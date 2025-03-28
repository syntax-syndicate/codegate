"""Command-line interface for codegate."""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Dict, Optional

import click
import structlog
from uvicorn.config import Config as UvicornConfig
from uvicorn.server import Server

import codegate
from codegate.ca.codegate_ca import CertificateAuthority
from codegate.codegate_logging import LogFormat, LogLevel, setup_logging
from codegate.config import Config, ConfigurationError
from codegate.db.connection import (
    init_db_sync,
    init_instance,
    init_session_if_not_exists,
)
from codegate.pipeline.factory import PipelineFactory
from codegate.pipeline.sensitive_data.manager import SensitiveDataManager
from codegate.providers import crud as provendcrud
from codegate.providers.copilot.provider import CopilotProvider
from codegate.server import init_app
from codegate.storage.utils import restore_storage_backup
from codegate.updates.client import init_update_client_singleton
from codegate.updates.scheduled import ScheduledUpdateChecker
from codegate.workspaces import crud as wscrud


class UvicornServer:
    def __init__(self, config: UvicornConfig, server: Server):
        self.server = server
        self.config = config
        self.port = config.port
        self.host = config.host
        self.log_level = config.log_level
        self.log_config = None
        self._startup_complete = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self._should_exit = False
        self.logger = structlog.get_logger("codegate").bind(origin="generic_server")

    async def serve(self) -> None:
        """Start the uvicorn server and handle shutdown gracefully."""
        self.logger.debug(f"Starting server on {self.host}:{self.port}")

        # Set up signal handlers
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self.cleanup()))
        loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self.cleanup()))

        self.server = Server(config=self.config)
        self.server.force_exit = True

        try:
            self._startup_complete.set()
            await self.server.serve()
        except asyncio.CancelledError:
            self.logger.info("Server received cancellation")
        except Exception as e:
            self.logger.exception("Unexpected error occurred during server execution", exc_info=e)
        finally:
            await self.cleanup()

    async def wait_startup_complete(self) -> None:
        """Wait for the server to complete startup."""
        self.logger.debug("Waiting for server startup to complete")
        await self._startup_complete.wait()

    async def cleanup(self) -> None:
        """Cleanup server resources and ensure graceful shutdown."""
        self.logger.debug("Cleaning up server resources")
        if not self._should_exit:
            self._should_exit = True
            self.logger.debug("Initiating server shutdown")
            self._shutdown_event.set()

            if hasattr(self.server, "shutdown"):
                self.logger.debug("Shutting down server")
                await self.server.shutdown()

            # Ensure all connections are closed
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            [task.cancel() for task in tasks]

            await asyncio.gather(*tasks, return_exceptions=True)
            self.logger.debug("Server shutdown complete")


def validate_port(ctx: click.Context, param: click.Parameter, value: int) -> int:
    """Validate the port number is in valid range."""
    cli_logger = structlog.get_logger("codegate").bind(origin="cli")
    cli_logger.debug(f"Validating port number: {value}")
    if value is not None and not (1 <= value <= 65535):
        raise click.BadParameter("Port must be between 1 and 65535")
    return value


@click.group()
@click.version_option()
def cli() -> None:
    """CodeGate - A configurable service gateway."""
    pass


@cli.command()
@click.option(
    "--prompts",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    required=False,
    help="Path to YAML prompts file (optional, shows default prompts if not provided)",
)
def show_prompts(prompts: Optional[Path]) -> None:
    """Display prompts from the specified file or default if no file specified."""
    try:
        cfg = Config.load(prompts_path=prompts)
        click.echo("Loaded prompts:")
        click.echo("-" * 40)
        for name, content in cfg.prompts.prompts.items():
            click.echo(f"\n{name}:")
            click.echo(f"{content}")
            click.echo("-" * 40)
    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--port",
    type=int,
    default=None,
    callback=validate_port,
    help="Port to listen on (default: 8989)",
)
@click.option(
    "--proxy-port",
    type=int,
    default=None,
    callback=validate_port,
    help="Proxy port to listen on (default: 8990)",
)
@click.option(
    "--host",
    type=str,
    default=None,
    help="Host to bind to (default: localhost)",
)
@click.option(
    "--log-level",
    type=click.Choice([level.value for level in LogLevel]),
    default=None,
    help="Set the log level (default: INFO)",
)
@click.option(
    "--log-format",
    type=click.Choice([fmt.value for fmt in LogFormat], case_sensitive=False),
    default=None,
    help="Set the log format (default: JSON)",
)
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to YAML config file",
)
@click.option(
    "--prompts",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help="Path to YAML prompts file",
)
@click.option(
    "--vllm-url",
    type=str,
    default=None,
    help="vLLM provider URL (default: http://localhost:8000/v1)",
)
@click.option(
    "--openai-url",
    type=str,
    default=None,
    help="OpenAI provider URL (default: https://api.openai.com/v1)",
)
@click.option(
    "--anthropic-url",
    type=str,
    default=None,
    help="Anthropic provider URL (default: https://api.anthropic.com/v1)",
)
@click.option(
    "--ollama-url",
    type=str,
    default=None,
    help="Ollama provider URL (default: http://localhost:11434/)",
)
@click.option(
    "--lm-studio-url",
    type=str,
    default=None,
    help="LM Studio provider URL (default: http://localhost:1234/)",
)
@click.option(
    "--model-base-path",
    type=str,
    default="./codegate_volume/models",
    help="Path to the model base directory",
)
@click.option(
    "--embedding-model",
    type=str,
    default="all-minilm-L6-v2-q5_k_m.gguf",
    help="Name of the model to use for embeddings",
)
@click.option(
    "--certs-dir",
    type=str,
    default=None,
    help="Directory for certificate files (default: ./certs)",
)
@click.option(
    "--ca-cert",
    type=str,
    default=None,
    help="CA certificate file name (default: ca.crt)",
)
@click.option(
    "--ca-key",
    type=str,
    default=None,
    help="CA key file name (default: ca.key)",
)
@click.option(
    "--server-cert",
    type=str,
    default=None,
    help="Server certificate file name (default: server.crt)",
)
@click.option(
    "--server-key",
    type=str,
    default=None,
    help="Server key file name (default: server.key)",
)
@click.option(
    "--db-path",
    type=str,
    default=None,
    help="Path to the main SQLite database file (default: ./codegate_volume/db/codegate.db)",
)
@click.option(
    "--vec-db-path",
    type=str,
    default=None,
    help="Path to the vector SQLite database file (default: ./sqlite_data/vectordb.db)",
)
def serve(  # noqa: C901
    port: Optional[int],
    proxy_port: Optional[int],
    host: Optional[str],
    log_level: Optional[str],
    log_format: Optional[str],
    config: Optional[Path],
    prompts: Optional[Path],
    vllm_url: Optional[str],
    openai_url: Optional[str],
    anthropic_url: Optional[str],
    ollama_url: Optional[str],
    lm_studio_url: Optional[str],
    model_base_path: Optional[str],
    embedding_model: Optional[str],
    db_path: Optional[str],
    vec_db_path: Optional[str],
    certs_dir: Optional[str],
    ca_cert: Optional[str],
    ca_key: Optional[str],
    server_cert: Optional[str],
    server_key: Optional[str],
) -> None:
    """Start the codegate server."""
    try:
        # Create provider URLs dict from CLI options
        cli_provider_urls: Dict[str, str] = {}
        if vllm_url:
            cli_provider_urls["vllm"] = vllm_url
        if openai_url:
            cli_provider_urls["openai"] = openai_url
        if anthropic_url:
            cli_provider_urls["anthropic"] = anthropic_url
        if ollama_url:
            cli_provider_urls["ollama"] = ollama_url
        if lm_studio_url:
            cli_provider_urls["lm_studio"] = lm_studio_url

        # Load configuration with priority resolution
        cfg = Config.load(
            config_path=config,
            prompts_path=prompts,
            cli_port=port,
            cli_proxy_port=proxy_port,
            cli_host=host,
            cli_log_level=log_level,
            cli_log_format=log_format,
            cli_provider_urls=cli_provider_urls,
            model_base_path=model_base_path,
            embedding_model=embedding_model,
            certs_dir=certs_dir,
            ca_cert=ca_cert,
            ca_key=ca_key,
            server_cert=server_cert,
            server_key=server_key,
            db_path=db_path,
            vec_db_path=vec_db_path,
        )

        # Set up logging first
        setup_logging(cfg.log_level, cfg.log_format)
        logger = structlog.get_logger("codegate").bind(origin="cli")

        init_db_sync(cfg.db_path)
        instance_id = init_instance(cfg.db_path)
        init_session_if_not_exists(cfg.db_path)

        # Initialize the update checking logic.
        update_client = init_update_client_singleton(
            cfg.update_service_url, codegate.__version__, instance_id
        )
        update_checker = ScheduledUpdateChecker(update_client)
        update_checker.daemon = True
        update_checker.start()

        # Check certificates and create CA if necessary
        logger.info("Checking certificates and creating CA if needed")
        ca = CertificateAuthority.get_instance()

        certs_check = ca.check_and_ensure_certificates()
        if not certs_check:
            click.echo("New Certificates generated successfully.")
        else:
            click.echo("Existing Certificates are already present.")

        # Initialize secrets manager and pipeline factory
        sensitive_data_manager = SensitiveDataManager()
        pipeline_factory = PipelineFactory(sensitive_data_manager)

        app = init_app(pipeline_factory)

        # Set up event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        registry = app.provider_registry
        loop.run_until_complete(provendcrud.initialize_provider_endpoints(registry))
        wsc = wscrud.WorkspaceCrud()
        loop.run_until_complete(wsc.initialize_mux_registry())

        # Run the server
        try:
            loop.run_until_complete(run_servers(cfg, app))
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, shutting down...")
        finally:
            loop.close()

    except ConfigurationError as e:
        click.echo(f"Configuration error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        logger = structlog.get_logger("codegate").bind(origin="cli")
        logger.exception("Unexpected error occurred")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


async def run_servers(cfg: Config, app) -> None:
    """Run the codegate server."""
    try:
        logger = structlog.get_logger("codegate").bind(origin="cli")
        logger.info(
            "Starting server",
            extra={
                "host": cfg.host,
                "port": cfg.port,
                "proxy_port": cfg.proxy_port,
                "log_level": cfg.log_level.value,
                "log_format": cfg.log_format.value,
                "prompts_loaded": len(cfg.prompts.prompts),
                "provider_urls": cfg.provider_urls,
                "model_base_path": cfg.model_base_path,
                "embedding_model": cfg.embedding_model,
                "certs_dir": cfg.certs_dir,
                "db_path": cfg.db_path,
                "vec_db_path": cfg.vec_db_path,
            },
        )

        # Create Uvicorn configuration
        uvicorn_config = UvicornConfig(
            app,
            host=cfg.host,
            port=cfg.port,
            log_level=cfg.log_level.value.lower(),
            log_config=None,  # Default logging configuration
        )

        server = UvicornServer(uvicorn_config, Server(config=uvicorn_config))

        # Initialize CopilotProvider and call run_proxy_server
        copilot_provider = CopilotProvider(cfg)

        tasks = [
            asyncio.create_task(server.serve()),  # Uvicorn server
            asyncio.create_task(copilot_provider.run_proxy_server()),  # Proxy server
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("Server received cancellation")
        except Exception as e:
            logger.exception("Unexpected error occurred during server execution", exc_info=e)
        finally:
            await server.cleanup()
            # Cleanup
            for task in tasks:
                if not task.done():
                    task.cancel()
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except asyncio.CancelledError:
                pass

    except Exception as e:
        logger.exception("Error running servers")
        raise e


@cli.command()
@click.option(
    "--backup-path",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    required=True,
    help="Directory path where the backup file is located.",
)
@click.option(
    "--backup-name",
    type=str,
    required=True,
    help="Name of the backup file to restore.",
)
def restore_backup(backup_path: Path, backup_name: str) -> None:
    """Restore the database from the specified backup."""
    try:
        restore_storage_backup(backup_path, backup_name)
        click.echo(f"Successfully restored the backup '{backup_name}' from {backup_path}.")
    except Exception as e:
        click.echo(f"Error restoring backup: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--certs-out-dir",
    type=click.Path(exists=False, file_okay=False, path_type=Path),
    help="Directory path where the certificates are going to be generated.",
)
@click.option(
    "--ca-cert-name",
    type=str,
    default=None,
    help="Name that will be given to the created ca-cert.",
)
@click.option(
    "--ca-key-name",
    type=str,
    default=None,
    help="Name that will be given to the created ca-key.",
)
@click.option(
    "--server-cert-name",
    type=str,
    default=None,
    help="Name that will be given to the created server-cert.",
)
@click.option(
    "--server-key-name",
    type=str,
    default=None,
    help="Name that will be given to the created server-key.",
)
@click.option(
    "--force-certs",
    is_flag=True,
    default=False,
    help=(
        "Force the generation of certificates even if they already exist. "
        "Warning: this will overwrite existing certificates."
    ),
)
@click.option(
    "--log-level",
    type=click.Choice([level.value for level in LogLevel]),
    default=None,
    help="Set the log level (default: INFO)",
)
@click.option(
    "--log-format",
    type=click.Choice([fmt.value for fmt in LogFormat], case_sensitive=False),
    default=None,
    help="Set the log format (default: JSON)",
)
def generate_certs(
    certs_out_dir: Optional[Path],
    ca_cert_name: Optional[str],
    ca_key_name: Optional[str],
    server_cert_name: Optional[str],
    server_key_name: Optional[str],
    force_certs: bool,
    log_level: Optional[str],
    log_format: Optional[str],
) -> None:
    """Generate certificates for the codegate server."""
    cfg = Config.load(
        certs_dir=certs_out_dir,
        ca_cert=ca_cert_name,
        ca_key=ca_key_name,
        server_cert=server_cert_name,
        server_key=server_key_name,
        force_certs=force_certs,
        cli_log_level=log_level,
        cli_log_format=log_format,
    )
    setup_logging(cfg.log_level, cfg.log_format)
    logger = structlog.get_logger("codegate").bind(origin="cli")

    ca = CertificateAuthority.get_instance()

    # Remove and regenerate certificates if forced; otherwise, just ensure they exist
    logger.info("Checking certificates and creating certs if needed")
    if force_certs:
        ca.remove_certificates()

    certs_check = ca.check_and_ensure_certificates()
    if not certs_check:
        logger.info("New Certificates generated successfully.")
    else:
        logger.info("Existing Certificates are already present.")


def main() -> None:
    """Main entry point for the CLI."""
    cli()


if __name__ == "__main__":
    main()

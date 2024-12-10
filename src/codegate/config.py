"""Configuration management for codegate."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Union

import structlog
import yaml

from codegate.codegate_logging import LogFormat, LogLevel
from codegate.exceptions import ConfigurationError
from codegate.prompts import PromptConfig

logger = structlog.get_logger("codegate")

# Default provider URLs
DEFAULT_PROVIDER_URLS = {
    "openai": "https://api.openai.com/v1",
    "anthropic": "https://api.anthropic.com/v1",
    "vllm": "http://localhost:8000",  # Base URL without /v1 path
    "ollama": "http://localhost:11434",  # Default Ollama server URL
}


@dataclass
class Config:
    """Application configuration with priority resolution."""

    # Singleton instance of Config which is set in Config.load().
    # All consumers can call: Config.get_config() to get the config.
    __config = None

    port: int = 8989
    host: str = "localhost"
    log_level: LogLevel = LogLevel.INFO
    log_format: LogFormat = LogFormat.JSON
    prompts: PromptConfig = field(default_factory=PromptConfig)

    model_base_path: str = "./models"
    chat_model_n_ctx: int = 32768
    chat_model_n_gpu_layers: int = -1
    embedding_model: str = "all-minilm-L6-v2-q5_k_m.gguf"

    # Provider URLs with defaults
    provider_urls: Dict[str, str] = field(default_factory=lambda: DEFAULT_PROVIDER_URLS.copy())

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not isinstance(self.port, int) or not (1 <= self.port <= 65535):
            raise ConfigurationError("Port must be between 1 and 65535")

        if not isinstance(self.log_level, LogLevel):
            try:
                self.log_level = LogLevel(self.log_level)
            except ValueError as e:
                raise ConfigurationError(f"Invalid log level: {e}")

        if not isinstance(self.log_format, LogFormat):
            try:
                self.log_format = LogFormat(self.log_format)
            except ValueError as e:
                raise ConfigurationError(f"Invalid log format: {e}")

    @staticmethod
    def _load_default_prompts() -> PromptConfig:
        """Load default prompts from prompts/default.yaml."""
        default_prompts_path = Path(__file__).parent.parent.parent / "prompts" / "default.yaml"
        try:
            return PromptConfig.from_file(default_prompts_path)
        except Exception as e:
            import logging

            logging.warning(f"Failed to load default prompts: {e}")
            return PromptConfig()

    @classmethod
    def from_file(cls, config_path: Union[str, Path]) -> "Config":
        """Load configuration from a YAML file.

        Args:
            config_path: Path to the YAML configuration file

        Returns:
            Config: Configuration instance

        Raises:
            ConfigurationError: If the file cannot be read or parsed
        """
        try:
            with open(config_path, "r") as f:
                config_data = yaml.safe_load(f)

            if not isinstance(config_data, dict):
                raise ConfigurationError("Config file must contain a YAML dictionary")

            # Start with default prompts
            prompts_config = cls._load_default_prompts()

            # Override with prompts from config if present
            if "prompts" in config_data:
                if isinstance(config_data["prompts"], dict):
                    prompts_config = PromptConfig(prompts=config_data.pop("prompts"))
                elif isinstance(config_data["prompts"], str):
                    # If prompts is a string, treat it as a path to a prompts file
                    prompts_path = Path(config_data.pop("prompts"))
                    if not prompts_path.is_absolute():
                        prompts_path = Path(config_path).parent / prompts_path
                    prompts_config = PromptConfig.from_file(prompts_path)

            # Get provider URLs from config
            provider_urls = DEFAULT_PROVIDER_URLS.copy()
            if "provider_urls" in config_data:
                provider_urls.update(config_data.pop("provider_urls"))

            return cls(
                port=config_data.get("port", cls.port),
                host=config_data.get("host", cls.host),
                log_level=config_data.get("log_level", cls.log_level.value),
                log_format=config_data.get("log_format", cls.log_format.value),
                model_base_path=config_data.get("model_base_path", cls.model_base_path),
                chat_model_n_ctx=config_data.get("chat_model_n_ctx", cls.chat_model_n_ctx),
                chat_model_n_gpu_layers=config_data.get(
                    "chat_model_n_gpu_layers", cls.chat_model_n_gpu_layers
                ),
                embedding_model=config_data.get("embedding_model", cls.embedding_model),
                prompts=prompts_config,
                provider_urls=provider_urls,
            )
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse config file: {e}")
        except OSError as e:
            raise ConfigurationError(f"Failed to read config file: {e}")

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables.

        Returns:
            Config: Configuration instance
        """
        try:
            # Start with default prompts
            config = cls(prompts=cls._load_default_prompts())

            if "CODEGATE_APP_PORT" in os.environ:
                config.port = int(os.environ["CODEGATE_APP_PORT"])
            if "CODEGATE_APP_HOST" in os.environ:
                config.host = os.environ["CODEGATE_APP_HOST"]
            if "CODEGATE_APP_LOG_LEVEL" in os.environ:
                config.log_level = LogLevel(os.environ["CODEGATE_APP_LOG_LEVEL"])
            if "CODEGATE_LOG_FORMAT" in os.environ:
                config.log_format = LogFormat(os.environ["CODEGATE_LOG_FORMAT"])
            if "CODEGATE_PROMPTS_FILE" in os.environ:
                config.prompts = PromptConfig.from_file(
                    os.environ["CODEGATE_PROMPTS_FILE"]
                )  # noqa: E501

            # Load provider URLs from environment variables
            for provider in DEFAULT_PROVIDER_URLS.keys():
                env_var = f"CODEGATE_PROVIDER_{provider.upper()}_URL"
                if env_var in os.environ:
                    config.provider_urls[provider] = os.environ[env_var]

            return config
        except ValueError as e:
            raise ConfigurationError(f"Invalid environment variable value: {e}")

    @classmethod
    def load(
        cls,
        config_path: Optional[Union[str, Path]] = None,
        prompts_path: Optional[Union[str, Path]] = None,
        cli_port: Optional[int] = None,
        cli_host: Optional[str] = None,
        cli_log_level: Optional[str] = None,
        cli_log_format: Optional[str] = None,
        cli_provider_urls: Optional[Dict[str, str]] = None,
        model_base_path: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ) -> "Config":
        """Load configuration with priority resolution.

        Priority order (highest to lowest):
        1. CLI arguments
        2. Environment variables
        3. Config file
        4. Default values (including default prompts from prompts/default.yaml)

        Args:
            config_path: Optional path to config file
            prompts_path: Optional path to prompts file
            cli_port: Optional CLI port override
            cli_host: Optional CLI host override
            cli_log_level: Optional CLI log level override
            cli_log_format: Optional CLI log format override
            cli_provider_urls: Optional dict of provider URLs from CLI
            model_base_path: Optional path to model base directory
            embedding_model: Optional name of the model to use for embeddings

        Returns:
            Config: Resolved configuration

        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Start with defaults (including default prompts)
        config = cls(prompts=cls._load_default_prompts())

        # Load from config file if provided
        if config_path:
            try:
                config = cls.from_file(config_path)
            except ConfigurationError as e:
                # Log warning but continue with defaults
                logger.warning(f"Failed to load config file: {e}")

        # Override with environment variables
        env_config = cls.from_env()
        if "CODEGATE_APP_PORT" in os.environ:
            config.port = env_config.port
        if "CODEGATE_APP_HOST" in os.environ:
            config.host = env_config.host
        if "CODEGATE_APP_LOG_LEVEL" in os.environ:
            config.log_level = env_config.log_level
        if "CODEGATE_LOG_FORMAT" in os.environ:
            config.log_format = env_config.log_format
        if "CODEGATE_PROMPTS_FILE" in os.environ:
            config.prompts = env_config.prompts
        if "CODEGATE_MODEL_BASE_PATH" in os.environ:
            config.model_base_path = env_config.model_base_path
        if "CODEGATE_EMBEDDING_MODEL" in os.environ:
            config.embedding_model = env_config.embedding_model

        # Override provider URLs from environment
        for provider, url in env_config.provider_urls.items():
            config.provider_urls[provider] = url

        # Override with CLI arguments
        if cli_port is not None:
            config.port = cli_port
        if cli_host is not None:
            config.host = cli_host
        if cli_log_level is not None:
            config.log_level = LogLevel(cli_log_level)
        if cli_log_format is not None:
            config.log_format = LogFormat(cli_log_format)
        if prompts_path is not None:
            config.prompts = PromptConfig.from_file(prompts_path)
        if cli_provider_urls is not None:
            config.provider_urls.update(cli_provider_urls)
        if model_base_path is not None:
            config.model_base_path = model_base_path
        if embedding_model is not None:
            config.embedding_model = embedding_model

        # Set the __config class attribute
        Config.__config = config

        return config

    @classmethod
    def get_config(cls):
        return cls.__config

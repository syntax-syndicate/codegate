# Code generated by sqlc. DO NOT EDIT.
# versions:
#   sqlc v1.27.0
# source: queries.sql
import dataclasses
from typing import Any, AsyncIterator, Iterator, Optional

import sqlalchemy
import sqlalchemy.ext.asyncio

from codegate.db import models


CREATE_ALERT = """-- name: create_alert \\:one
INSERT INTO alerts (
    id,
    prompt_id,
    output_id,
    code_snippet,
    trigger_string,
    trigger_type,
    trigger_category,
    timestamp
) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING id, prompt_id, output_id, code_snippet, trigger_string, trigger_type, trigger_category, timestamp
"""


@dataclasses.dataclass()
class CreateAlertParams:
    id: Any
    prompt_id: Any
    output_id: Any
    code_snippet: Any
    trigger_string: Any
    trigger_type: Any
    trigger_category: Optional[Any]
    timestamp: Any


CREATE_OUTPUT = """-- name: create_output \\:one
INSERT INTO outputs (
    id,
    prompt_id,
    timestamp,
    output,
    status
) VALUES (?, ?, ?, ?, ?) RETURNING id, prompt_id, timestamp, output, status
"""


CREATE_PROMPT = """-- name: create_prompt \\:one
INSERT INTO prompts (
    id,
    timestamp,
    provider,
    system_prompt,
    user_prompt,
    type,
    status
) VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING id, timestamp, provider, system_prompt, user_prompt, type, status
"""


@dataclasses.dataclass()
class CreatePromptParams:
    id: Any
    timestamp: Any
    provider: Optional[Any]
    system_prompt: Optional[Any]
    user_prompt: Any
    type: Any
    status: Any


GET_ALERT = """-- name: get_alert \\:one
SELECT id, prompt_id, output_id, code_snippet, trigger_string, trigger_type, trigger_category, timestamp FROM alerts WHERE id = ?
"""


GET_OUTPUT = """-- name: get_output \\:one
SELECT id, prompt_id, timestamp, output, status FROM outputs WHERE id = ?
"""


GET_OUTPUTS_BY_PROMPT_ID = """-- name: get_outputs_by_prompt_id \\:many
SELECT id, prompt_id, timestamp, output, status FROM outputs 
WHERE prompt_id = ? 
ORDER BY timestamp DESC
"""


GET_PROMPT = """-- name: get_prompt \\:one
SELECT id, timestamp, provider, system_prompt, user_prompt, type, status FROM prompts WHERE id = ?
"""


GET_PROMPT_WITH_OUTPUTS_AND_ALERTS = """-- name: get_prompt_with_outputs_and_alerts \\:many
SELECT 
    p.id, p.timestamp, p.provider, p.system_prompt, p.user_prompt, p.type, p.status,
    o.id as output_id,
    o.output,
    o.status as output_status,
    a.id as alert_id,
    a.code_snippet,
    a.trigger_string,
    a.trigger_type,
    a.trigger_category
FROM prompts p
LEFT JOIN outputs o ON p.id = o.prompt_id
LEFT JOIN alerts a ON p.id = a.prompt_id
WHERE p.id = ?
ORDER BY o.timestamp DESC, a.timestamp DESC
"""


@dataclasses.dataclass()
class GetPromptWithOutputsAndAlertsRow:
    id: Any
    timestamp: Any
    provider: Optional[Any]
    system_prompt: Optional[Any]
    user_prompt: Any
    type: Any
    status: Any
    output_id: Optional[Any]
    output: Optional[Any]
    output_status: Optional[Any]
    alert_id: Optional[Any]
    code_snippet: Optional[Any]
    trigger_string: Optional[Any]
    trigger_type: Optional[Any]
    trigger_category: Optional[Any]


GET_SETTINGS = """-- name: get_settings \\:one
SELECT id, ip, port, llm_model, system_prompt, other_settings FROM settings ORDER BY id LIMIT 1
"""


LIST_ALERTS_BY_PROMPT = """-- name: list_alerts_by_prompt \\:many
SELECT id, prompt_id, output_id, code_snippet, trigger_string, trigger_type, trigger_category, timestamp FROM alerts 
WHERE prompt_id = ? 
ORDER BY timestamp DESC
"""


LIST_PROMPTS = """-- name: list_prompts \\:many
SELECT id, timestamp, provider, system_prompt, user_prompt, type, status FROM prompts 
ORDER BY timestamp DESC 
LIMIT ? OFFSET ?
"""


UPSERT_SETTINGS = """-- name: upsert_settings \\:one
INSERT INTO settings (
    id,
    ip,
    port,
    llm_model,
    system_prompt,
    other_settings
) VALUES (?, ?, ?, ?, ?, ?)
ON CONFLICT(id) DO UPDATE SET
    ip = excluded.ip,
    port = excluded.port,
    llm_model = excluded.llm_model,
    system_prompt = excluded.system_prompt,
    other_settings = excluded.other_settings
RETURNING id, ip, port, llm_model, system_prompt, other_settings
"""


@dataclasses.dataclass()
class UpsertSettingsParams:
    id: Any
    ip: Optional[Any]
    port: Optional[Any]
    llm_model: Optional[Any]
    system_prompt: Optional[Any]
    other_settings: Optional[Any]


class Querier:
    def __init__(self, conn: sqlalchemy.engine.Connection):
        self._conn = conn

    def create_alert(self, arg: CreateAlertParams) -> Optional[models.Alert]:
        row = self._conn.execute(sqlalchemy.text(CREATE_ALERT), {
            "p1": arg.id,
            "p2": arg.prompt_id,
            "p3": arg.output_id,
            "p4": arg.code_snippet,
            "p5": arg.trigger_string,
            "p6": arg.trigger_type,
            "p7": arg.trigger_category,
            "p8": arg.timestamp,
        }).first()
        if row is None:
            return None
        return models.Alert(
            id=row[0],
            prompt_id=row[1],
            output_id=row[2],
            code_snippet=row[3],
            trigger_string=row[4],
            trigger_type=row[5],
            trigger_category=row[6],
            timestamp=row[7],
        )

    def create_output(self, *, id: Any, prompt_id: Any, timestamp: Any, output: Any, status: Any) -> Optional[models.Output]:
        row = self._conn.execute(sqlalchemy.text(CREATE_OUTPUT), {
            "p1": id,
            "p2": prompt_id,
            "p3": timestamp,
            "p4": output,
            "p5": status,
        }).first()
        if row is None:
            return None
        return models.Output(
            id=row[0],
            prompt_id=row[1],
            timestamp=row[2],
            output=row[3],
            status=row[4],
        )

    def create_prompt(self, arg: CreatePromptParams) -> Optional[models.Prompt]:
        row = self._conn.execute(sqlalchemy.text(CREATE_PROMPT), {
            "p1": arg.id,
            "p2": arg.timestamp,
            "p3": arg.provider,
            "p4": arg.system_prompt,
            "p5": arg.user_prompt,
            "p6": arg.type,
            "p7": arg.status,
        }).first()
        if row is None:
            return None
        return models.Prompt(
            id=row[0],
            timestamp=row[1],
            provider=row[2],
            system_prompt=row[3],
            user_prompt=row[4],
            type=row[5],
            status=row[6],
        )

    def get_alert(self, *, id: Any) -> Optional[models.Alert]:
        row = self._conn.execute(sqlalchemy.text(GET_ALERT), {"p1": id}).first()
        if row is None:
            return None
        return models.Alert(
            id=row[0],
            prompt_id=row[1],
            output_id=row[2],
            code_snippet=row[3],
            trigger_string=row[4],
            trigger_type=row[5],
            trigger_category=row[6],
            timestamp=row[7],
        )

    def get_output(self, *, id: Any) -> Optional[models.Output]:
        row = self._conn.execute(sqlalchemy.text(GET_OUTPUT), {"p1": id}).first()
        if row is None:
            return None
        return models.Output(
            id=row[0],
            prompt_id=row[1],
            timestamp=row[2],
            output=row[3],
            status=row[4],
        )

    def get_outputs_by_prompt_id(self, *, prompt_id: Any) -> Iterator[models.Output]:
        result = self._conn.execute(sqlalchemy.text(GET_OUTPUTS_BY_PROMPT_ID), {"p1": prompt_id})
        for row in result:
            yield models.Output(
                id=row[0],
                prompt_id=row[1],
                timestamp=row[2],
                output=row[3],
                status=row[4],
            )

    def get_prompt(self, *, id: Any) -> Optional[models.Prompt]:
        row = self._conn.execute(sqlalchemy.text(GET_PROMPT), {"p1": id}).first()
        if row is None:
            return None
        return models.Prompt(
            id=row[0],
            timestamp=row[1],
            provider=row[2],
            system_prompt=row[3],
            user_prompt=row[4],
            type=row[5],
            status=row[6],
        )

    def get_prompt_with_outputs_and_alerts(self, *, id: Any) -> Iterator[GetPromptWithOutputsAndAlertsRow]:
        result = self._conn.execute(sqlalchemy.text(GET_PROMPT_WITH_OUTPUTS_AND_ALERTS), {"p1": id})
        for row in result:
            yield GetPromptWithOutputsAndAlertsRow(
                id=row[0],
                timestamp=row[1],
                provider=row[2],
                system_prompt=row[3],
                user_prompt=row[4],
                type=row[5],
                status=row[6],
                output_id=row[7],
                output=row[8],
                output_status=row[9],
                alert_id=row[10],
                code_snippet=row[11],
                trigger_string=row[12],
                trigger_type=row[13],
                trigger_category=row[14],
            )

    def get_settings(self) -> Optional[models.Setting]:
        row = self._conn.execute(sqlalchemy.text(GET_SETTINGS)).first()
        if row is None:
            return None
        return models.Setting(
            id=row[0],
            ip=row[1],
            port=row[2],
            llm_model=row[3],
            system_prompt=row[4],
            other_settings=row[5],
        )

    def list_alerts_by_prompt(self, *, prompt_id: Any) -> Iterator[models.Alert]:
        result = self._conn.execute(sqlalchemy.text(LIST_ALERTS_BY_PROMPT), {"p1": prompt_id})
        for row in result:
            yield models.Alert(
                id=row[0],
                prompt_id=row[1],
                output_id=row[2],
                code_snippet=row[3],
                trigger_string=row[4],
                trigger_type=row[5],
                trigger_category=row[6],
                timestamp=row[7],
            )

    def list_prompts(self, *, limit: Any, offset: Any) -> Iterator[models.Prompt]:
        result = self._conn.execute(sqlalchemy.text(LIST_PROMPTS), {"p1": limit, "p2": offset})
        for row in result:
            yield models.Prompt(
                id=row[0],
                timestamp=row[1],
                provider=row[2],
                system_prompt=row[3],
                user_prompt=row[4],
                type=row[5],
                status=row[6],
            )

    def upsert_settings(self, arg: UpsertSettingsParams) -> Optional[models.Setting]:
        row = self._conn.execute(sqlalchemy.text(UPSERT_SETTINGS), {
            "p1": arg.id,
            "p2": arg.ip,
            "p3": arg.port,
            "p4": arg.llm_model,
            "p5": arg.system_prompt,
            "p6": arg.other_settings,
        }).first()
        if row is None:
            return None
        return models.Setting(
            id=row[0],
            ip=row[1],
            port=row[2],
            llm_model=row[3],
            system_prompt=row[4],
            other_settings=row[5],
        )


class AsyncQuerier:
    def __init__(self, conn: sqlalchemy.ext.asyncio.AsyncConnection):
        self._conn = conn

    async def create_alert(self, arg: CreateAlertParams) -> Optional[models.Alert]:
        row = (await self._conn.execute(sqlalchemy.text(CREATE_ALERT), {
            "p1": arg.id,
            "p2": arg.prompt_id,
            "p3": arg.output_id,
            "p4": arg.code_snippet,
            "p5": arg.trigger_string,
            "p6": arg.trigger_type,
            "p7": arg.trigger_category,
            "p8": arg.timestamp,
        })).first()
        if row is None:
            return None
        return models.Alert(
            id=row[0],
            prompt_id=row[1],
            output_id=row[2],
            code_snippet=row[3],
            trigger_string=row[4],
            trigger_type=row[5],
            trigger_category=row[6],
            timestamp=row[7],
        )

    async def create_output(self, *, id: Any, prompt_id: Any, timestamp: Any, output: Any, status: Any) -> Optional[models.Output]:
        row = (await self._conn.execute(sqlalchemy.text(CREATE_OUTPUT), {
            "p1": id,
            "p2": prompt_id,
            "p3": timestamp,
            "p4": output,
            "p5": status,
        })).first()
        if row is None:
            return None
        return models.Output(
            id=row[0],
            prompt_id=row[1],
            timestamp=row[2],
            output=row[3],
            status=row[4],
        )

    async def create_prompt(self, arg: CreatePromptParams) -> Optional[models.Prompt]:
        row = (await self._conn.execute(sqlalchemy.text(CREATE_PROMPT), {
            "p1": arg.id,
            "p2": arg.timestamp,
            "p3": arg.provider,
            "p4": arg.system_prompt,
            "p5": arg.user_prompt,
            "p6": arg.type,
            "p7": arg.status,
        })).first()
        if row is None:
            return None
        return models.Prompt(
            id=row[0],
            timestamp=row[1],
            provider=row[2],
            system_prompt=row[3],
            user_prompt=row[4],
            type=row[5],
            status=row[6],
        )

    async def get_alert(self, *, id: Any) -> Optional[models.Alert]:
        row = (await self._conn.execute(sqlalchemy.text(GET_ALERT), {"p1": id})).first()
        if row is None:
            return None
        return models.Alert(
            id=row[0],
            prompt_id=row[1],
            output_id=row[2],
            code_snippet=row[3],
            trigger_string=row[4],
            trigger_type=row[5],
            trigger_category=row[6],
            timestamp=row[7],
        )

    async def get_output(self, *, id: Any) -> Optional[models.Output]:
        row = (await self._conn.execute(sqlalchemy.text(GET_OUTPUT), {"p1": id})).first()
        if row is None:
            return None
        return models.Output(
            id=row[0],
            prompt_id=row[1],
            timestamp=row[2],
            output=row[3],
            status=row[4],
        )

    async def get_outputs_by_prompt_id(self, *, prompt_id: Any) -> AsyncIterator[models.Output]:
        result = await self._conn.stream(sqlalchemy.text(GET_OUTPUTS_BY_PROMPT_ID), {"p1": prompt_id})
        async for row in result:
            yield models.Output(
                id=row[0],
                prompt_id=row[1],
                timestamp=row[2],
                output=row[3],
                status=row[4],
            )

    async def get_prompt(self, *, id: Any) -> Optional[models.Prompt]:
        row = (await self._conn.execute(sqlalchemy.text(GET_PROMPT), {"p1": id})).first()
        if row is None:
            return None
        return models.Prompt(
            id=row[0],
            timestamp=row[1],
            provider=row[2],
            system_prompt=row[3],
            user_prompt=row[4],
            type=row[5],
            status=row[6],
        )

    async def get_prompt_with_outputs_and_alerts(self, *, id: Any) -> AsyncIterator[GetPromptWithOutputsAndAlertsRow]:
        result = await self._conn.stream(sqlalchemy.text(GET_PROMPT_WITH_OUTPUTS_AND_ALERTS), {"p1": id})
        async for row in result:
            yield GetPromptWithOutputsAndAlertsRow(
                id=row[0],
                timestamp=row[1],
                provider=row[2],
                system_prompt=row[3],
                user_prompt=row[4],
                type=row[5],
                status=row[6],
                output_id=row[7],
                output=row[8],
                output_status=row[9],
                alert_id=row[10],
                code_snippet=row[11],
                trigger_string=row[12],
                trigger_type=row[13],
                trigger_category=row[14],
            )

    async def get_settings(self) -> Optional[models.Setting]:
        row = (await self._conn.execute(sqlalchemy.text(GET_SETTINGS))).first()
        if row is None:
            return None
        return models.Setting(
            id=row[0],
            ip=row[1],
            port=row[2],
            llm_model=row[3],
            system_prompt=row[4],
            other_settings=row[5],
        )

    async def list_alerts_by_prompt(self, *, prompt_id: Any) -> AsyncIterator[models.Alert]:
        result = await self._conn.stream(sqlalchemy.text(LIST_ALERTS_BY_PROMPT), {"p1": prompt_id})
        async for row in result:
            yield models.Alert(
                id=row[0],
                prompt_id=row[1],
                output_id=row[2],
                code_snippet=row[3],
                trigger_string=row[4],
                trigger_type=row[5],
                trigger_category=row[6],
                timestamp=row[7],
            )

    async def list_prompts(self, *, limit: Any, offset: Any) -> AsyncIterator[models.Prompt]:
        result = await self._conn.stream(sqlalchemy.text(LIST_PROMPTS), {"p1": limit, "p2": offset})
        async for row in result:
            yield models.Prompt(
                id=row[0],
                timestamp=row[1],
                provider=row[2],
                system_prompt=row[3],
                user_prompt=row[4],
                type=row[5],
                status=row[6],
            )

    async def upsert_settings(self, arg: UpsertSettingsParams) -> Optional[models.Setting]:
        row = (await self._conn.execute(sqlalchemy.text(UPSERT_SETTINGS), {
            "p1": arg.id,
            "p2": arg.ip,
            "p3": arg.port,
            "p4": arg.llm_model,
            "p5": arg.system_prompt,
            "p6": arg.other_settings,
        })).first()
        if row is None:
            return None
        return models.Setting(
            id=row[0],
            ip=row[1],
            port=row[2],
            llm_model=row[3],
            system_prompt=row[4],
            other_settings=row[5],
        )

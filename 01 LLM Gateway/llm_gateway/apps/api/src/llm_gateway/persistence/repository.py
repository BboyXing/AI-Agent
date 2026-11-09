from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from llm_gateway.persistence.db import Database
from llm_gateway.schemas.usage import (
    AttemptRecord,
    CallDetail,
    CallPage,
    CallRecord,
    TraceRecord,
    UsageSummary,
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class UsageRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def start_request(
        self,
        *,
        request_id: str,
        endpoint: str,
        route: str,
        prompt: str,
        stream: bool,
        subject: str,
    ) -> None:
        await self.database.execute(
            """
            INSERT INTO llm_requests
                (request_id, endpoint, route, prompt, stream, subject, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
            """,
            (request_id, endpoint, route, prompt, int(stream), subject, utc_now()),
        )

    async def finish_request(
        self,
        request_id: str,
        *,
        status: str,
        selected_candidate: str | None,
        provider: str | None,
        upstream_model: str | None,
        input_tokens: int | None,
        output_tokens: int | None,
        total_tokens: int | None,
        latency_ms: int,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        await self.database.execute(
            """
            UPDATE llm_requests
            SET status = ?, selected_candidate = ?, provider = ?, upstream_model = ?,
                input_tokens = ?, output_tokens = ?, total_tokens = ?, latency_ms = ?,
                error_code = ?, error_message = ?, completed_at = ?
            WHERE request_id = ?
            """,
            (
                status,
                selected_candidate,
                provider,
                upstream_model,
                input_tokens,
                output_tokens,
                total_tokens,
                latency_ms,
                error_code,
                error_message,
                utc_now(),
                request_id,
            ),
        )

    async def start_attempt(
        self,
        *,
        request_id: str,
        ordinal: int,
        candidate: str,
        provider: str,
        upstream_model: str,
    ) -> int:
        return await self.database.execute(
            """
            INSERT INTO llm_attempts
                (request_id, ordinal, candidate, provider, upstream_model, status, started_at)
            VALUES (?, ?, ?, ?, ?, 'running', ?)
            """,
            (request_id, ordinal, candidate, provider, upstream_model, utc_now()),
        )

    async def finish_attempt(
        self,
        attempt_id: int,
        *,
        status: str,
        latency_ms: int,
        http_status: int | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
    ) -> None:
        await self.database.execute(
            """
            UPDATE llm_attempts
            SET status = ?, http_status = ?, error_code = ?, error_message = ?,
                latency_ms = ?, input_tokens = ?, output_tokens = ?, total_tokens = ?,
                completed_at = ?
            WHERE id = ?
            """,
            (
                status,
                http_status,
                error_code,
                error_message,
                latency_ms,
                input_tokens,
                output_tokens,
                total_tokens,
                utc_now(),
                attempt_id,
            ),
        )

    async def add_trace(
        self,
        *,
        request_id: str,
        event_type: str,
        attempt_id: int | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        await self.database.execute(
            """
            INSERT INTO trace_events
                (request_id, attempt_id, event_type, created_at, attributes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                request_id,
                attempt_id,
                event_type,
                utc_now(),
                json.dumps(attributes or {}, ensure_ascii=False, default=str),
            ),
        )

    async def summary(
        self,
        *,
        from_time: str,
        to_time: str,
        route: str | None = None,
        status: str | None = None,
    ) -> UsageSummary:
        clauses = ["created_at >= ?", "created_at < ?"]
        params: list[Any] = [from_time, to_time]
        if route:
            clauses.append("route = ?")
            params.append(route)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = " AND ".join(clauses)
        row = await self.database.fetchone(
            f"""
            SELECT
                COUNT(*) AS request_count,
                COALESCE(SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END), 0)
                    AS success_count,
                COALESCE(SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END), 0)
                    AS failure_count,
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(AVG(latency_ms), 0) AS average_latency_ms
            FROM llm_requests
            WHERE {where}
            """,
            params,
        )
        assert row is not None
        count = int(row["request_count"])
        success = int(row["success_count"])
        return UsageSummary(
            request_count=count,
            success_count=success,
            failure_count=int(row["failure_count"]),
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            total_tokens=int(row["total_tokens"]),
            success_rate=(success / count) if count else 0,
            average_latency_ms=float(row["average_latency_ms"]),
        )

    async def list_calls(
        self,
        *,
        limit: int,
        offset: int,
        route: str | None = None,
        status: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
    ) -> CallPage:
        clauses: list[str] = []
        params: list[Any] = []
        if route:
            clauses.append("route = ?")
            params.append(route)
        if status:
            clauses.append("status = ?")
            params.append(status)
        if from_time:
            clauses.append("created_at >= ?")
            params.append(from_time)
        if to_time:
            clauses.append("created_at < ?")
            params.append(to_time)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        count_row = await self.database.fetchone(
            f"SELECT COUNT(*) AS total FROM llm_requests {where}",
            params,
        )
        rows = await self.database.fetchall(
            f"""
            SELECT * FROM llm_requests
            {where}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        )
        return CallPage(
            items=[_call_record(row) for row in rows],
            total=int(count_row["total"]) if count_row else 0,
            limit=limit,
            offset=offset,
        )

    async def call_detail(self, request_id: str) -> CallDetail | None:
        row = await self.database.fetchone(
            "SELECT * FROM llm_requests WHERE request_id = ?",
            (request_id,),
        )
        if row is None:
            return None
        attempts = await self.database.fetchall(
            "SELECT * FROM llm_attempts WHERE request_id = ? ORDER BY ordinal",
            (request_id,),
        )
        trace = await self.database.fetchall(
            "SELECT * FROM trace_events WHERE request_id = ? ORDER BY id",
            (request_id,),
        )
        return CallDetail(
            **_call_record(row).model_dump(),
            attempts=[
                AttemptRecord(
                    id=int(item["id"]),
                    ordinal=int(item["ordinal"]),
                    candidate=item["candidate"],
                    provider=item["provider"],
                    upstream_model=item["upstream_model"],
                    status=item["status"],
                    http_status=item["http_status"],
                    error_code=item["error_code"],
                    error_message=item["error_message"],
                    latency_ms=item["latency_ms"],
                    input_tokens=item["input_tokens"],
                    output_tokens=item["output_tokens"],
                    total_tokens=item["total_tokens"],
                    started_at=item["started_at"],
                    completed_at=item["completed_at"],
                )
                for item in attempts
            ],
            trace=[
                TraceRecord(
                    event_type=item["event_type"],
                    created_at=item["created_at"],
                    attributes=json.loads(item["attributes"]),
                )
                for item in trace
            ],
        )


def _call_record(row: dict[str, Any]) -> CallRecord:
    return CallRecord(
        request_id=row["request_id"],
        endpoint=row["endpoint"],
        route=row["route"],
        prompt=row["prompt"],
        stream=bool(row["stream"]),
        subject=row["subject"],
        status=row["status"],
        selected_candidate=row["selected_candidate"],
        provider=row["provider"],
        upstream_model=row["upstream_model"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        total_tokens=row["total_tokens"],
        latency_ms=row["latency_ms"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        completed_at=row["completed_at"],
    )

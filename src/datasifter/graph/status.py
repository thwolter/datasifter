from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from datasifter.graph.progress import AttributeState, ProgressTracker
from datasifter.interfaces import JobRepository, ProgressSink
from datasifter.schemas import ExtractionStatusPayload, JobState, JobStatus, StatusEvent


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StatusEmitter:
    def __init__(
        self,
        *,
        job: JobState,
        job_repository: JobRepository,
        progress: ProgressTracker,
        attribute_states: dict[str, AttributeState],
        sink: ProgressSink | None = None,
    ) -> None:
        self._job = job
        self._repo = job_repository
        self._progress = progress
        self._attribute_states = attribute_states
        self._sink = sink
        self._lock = asyncio.Lock()

    async def emit(
        self,
        event: StatusEvent,
        *,
        status_override: JobStatus | None = None,
        attribute_payload: dict[str, Any] | None = None,
        provenance: dict[str, Any] | None = None,
        summary: str | None = None,
        errors: list[str] | None = None,
        include_snapshot: bool = False,
        results: dict[str, Any] | None = None,
    ) -> ExtractionStatusPayload:
        async with self._lock:
            seq = await self._repo.increment_sequence(self._job)
            self._job.seq = seq
            payload = ExtractionStatusPayload(
                seq=seq,
                timestamp=_utcnow(),
                job_id=self._job.job_id,
                doc_id=self._job.doc_id,
                doc_type=self._job.doc_type,
                event=event,
                status=status_override or self._job.status,
                progress=self._progress.snapshot() if include_snapshot else None,
                attribute=attribute_payload,
                provenance=provenance,
                summary=summary,
                errors=errors,
                attributes=[
                    state.to_progress() for state in self._attribute_states.values()
                ]
                if include_snapshot
                else None,
                results=results,
            )
            if self._sink is not None:
                await self._sink.publish(payload)
            return payload


__all__ = ["StatusEmitter"]

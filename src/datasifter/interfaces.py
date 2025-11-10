from __future__ import annotations

from typing import Protocol, Sequence

from .schemas import (
    AttributeResult,
    AttributeSpec,
    Candidate,
    ExtractionRequest,
    ExtractionStatusPayload,
    JobState,
    JobStatus,
    RetrievalConfig,
    RetrievedChunk,
)


class JobRepository(Protocol):
    async def prepare_job(
        self,
        *,
        request: ExtractionRequest,
        job: JobState | None,
        retrieval_config: RetrievalConfig,
        model_name: str,
        model_version: str,
    ) -> JobState: ...

    async def update_status(
        self,
        job: JobState,
        *,
        status: JobStatus,
        error: str | None = None,
    ) -> JobState: ...

    async def refresh(self, job: JobState) -> JobState: ...

    async def increment_sequence(self, job: JobState) -> int: ...


class AttributeStore(Protocol):
    async def persist(
        self, job: JobState, spec: AttributeSpec, result: AttributeResult
    ) -> None: ...


class RetrievalProvider(Protocol):
    async def retrieve(
        self,
        *,
        job: JobState,
        request: ExtractionRequest,
        attribute: AttributeSpec,
        config: RetrievalConfig,
    ) -> Sequence[RetrievedChunk]: ...


class MapEngine(Protocol):
    async def extract_candidate(
        self,
        *,
        doc_type: str,
        attribute: AttributeSpec,
        chunk: RetrievedChunk,
        attempt: int,
        prompt_id: str | None = None,
    ) -> Candidate: ...


class ProgressSink(Protocol):
    async def publish(self, payload: ExtractionStatusPayload) -> None: ...

from __future__ import annotations

from typing import Sequence

from datasifter.interfaces import (
    AttributeStore,
    JobRepository,
    MapEngine,
    ProgressSink,
    RetrievalProvider,
)
from datasifter.schemas import (
    AttributeResult,
    AttributeSpec,
    Candidate,
    ExtractionRequest,
    ExtractionStatusPayload,
    JobState,
    JobStatus,
    RetrievedChunk,
    RetrievalConfig,
)


class StubJobRepository(JobRepository):
    async def prepare_job(
        self,
        *,
        request: ExtractionRequest,
        job: JobState | None,
        retrieval_config: RetrievalConfig,
        model_name: str,
        model_version: str,
    ) -> JobState:
        raise NotImplementedError("Override prepare_job with persistence logic.")

    async def update_status(
        self,
        job: JobState,
        *,
        status: JobStatus,
        error: str | None = None,
    ) -> JobState:
        raise NotImplementedError("Override update_status with persistence logic.")

    async def refresh(self, job: JobState) -> JobState:
        raise NotImplementedError("Override refresh to load the latest job snapshot.")

    async def increment_sequence(self, job: JobState) -> int:
        raise NotImplementedError("Override increment_sequence to enforce ordering.")


class StubAttributeStore(AttributeStore):
    async def persist(
        self, job: JobState, spec: AttributeSpec, result: AttributeResult
    ) -> None:
        raise NotImplementedError("Implement persistence for attribute results.")


class StubRetrievalProvider(RetrievalProvider):
    async def retrieve(
        self,
        *,
        job: JobState,
        request: ExtractionRequest,
        attribute: AttributeSpec,
        config: RetrievalConfig,
    ) -> Sequence[RetrievedChunk]:
        raise NotImplementedError("Implement chunk retrieval before the map phase.")


class StubMapEngine(MapEngine):
    async def extract_candidate(
        self,
        *,
        doc_type: str,
        attribute: AttributeSpec,
        chunk: RetrievedChunk,
        attempt: int,
        prompt_id: str | None = None,
    ) -> Candidate:
        raise NotImplementedError("Bridge your LLM or rule-engine here.")


class StubProgressSink(ProgressSink):
    async def publish(self, payload: ExtractionStatusPayload) -> None:
        raise NotImplementedError("Forward status payloads to your observability stack.")


__all__ = [
    "StubJobRepository",
    "StubAttributeStore",
    "StubRetrievalProvider",
    "StubMapEngine",
    "StubProgressSink",
]

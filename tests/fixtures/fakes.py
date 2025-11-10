from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from datasifter.interfaces import JobRepository
from datasifter.schemas import (
    AttributeResult,
    AttributeSpec,
    Candidate,
    ExtractionStatusPayload,
    JobState,
    JobStatus,
    RetrievedChunk,
    RetrievalConfig,
    RetrievalMetadata,
)


class FakeJobRepository:
    def __init__(self, job: JobState) -> None:
        self.job = job
        self.seq = job.seq
        self.prepare_calls: list[dict[str, Any]] = []
        self.status_updates: list[tuple[JobStatus, str | None]] = []
        self.refresh_calls = 0
        self.increment_calls = 0

    async def prepare_job(
        self,
        *,
        request: Any,
        job: JobState | None,
        retrieval_config: RetrievalConfig,
        model_name: str,
        model_version: str,
    ) -> JobState:
        self.prepare_calls.append(
            {
                "request": request,
                "job": job,
                "retrieval_config": retrieval_config,
                "model_name": model_name,
                "model_version": model_version,
            }
        )
        if job is not None:
            self.job = job
        self.job.model = model_name
        self.job.model_version = model_version
        self.job.retriever_config = retrieval_config.model_dump(mode="json")
        return self.job

    async def update_status(
        self,
        job: JobState,
        *,
        status: JobStatus,
        error: str | None = None,
    ) -> JobState:
        self.job = job
        self.job.status = status
        self.job.error = error
        self.status_updates.append((status, error))
        if status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELED}:
            self.job.finished_at = datetime.utcnow()
        return self.job

    async def refresh(self, job: JobState) -> JobState:
        self.refresh_calls += 1
        return self.job

    async def increment_sequence(self, job: JobState) -> int:
        self.increment_calls += 1
        self.seq += 1
        self.job.seq = self.seq
        return self.seq


class FakeAttributeStore:
    def __init__(self) -> None:
        self.persisted: list[tuple[JobState, AttributeSpec, AttributeResult]] = []

    async def persist(
        self, job: JobState, spec: AttributeSpec, result: AttributeResult
    ) -> None:
        self.persisted.append((job, spec, result))


class FakeRetrievalProvider:
    def __init__(self, chunks: Sequence[RetrievedChunk]) -> None:
        self._chunks = list(chunks)
        self.calls: list[dict[str, Any]] = []

    async def retrieve(
        self,
        *,
        job: JobState,
        request: Any,
        attribute: AttributeSpec,
        config: RetrievalConfig,
    ) -> Sequence[RetrievedChunk]:
        self.calls.append(
            {
                "job": job,
                "request": request,
                "attribute": attribute,
                "config": config,
            }
        )
        return list(self._chunks)


class FakeMapEngine:
    def __init__(self, *, value: str | None = None, confidence: float = 0.9) -> None:
        self.calls: list[dict[str, Any]] = []
        self._value = value
        self._confidence = confidence

    async def extract_candidate(
        self,
        *,
        doc_type: str,
        attribute: AttributeSpec,
        chunk: RetrievedChunk,
        attempt: int,
        prompt_id: str | None = None,
    ) -> Candidate:
        metadata = RetrievalMetadata(
            chunk_id=chunk.chunk_id,
            header=chunk.header,
            page=chunk.page,
            retr_score=chunk.retr_score,
            text_excerpt=chunk.text,
        )
        candidate = Candidate(
            attribute=attribute.name,
            value=self._value or chunk.text,
            confidence_local=self._confidence,
            rationale=f"chunk:{chunk.chunk_id}",
            retrieval=metadata,
            raw_json={"attempt": attempt},
        )
        self.calls.append(
            {
                "doc_type": doc_type,
                "attribute": attribute,
                "chunk": chunk,
                "attempt": attempt,
                "prompt_id": prompt_id,
            }
        )
        return candidate


class FakeProgressSink:
    def __init__(self) -> None:
        self.published: list[ExtractionStatusPayload] = []

    async def publish(self, payload: ExtractionStatusPayload) -> None:
        self.published.append(payload)


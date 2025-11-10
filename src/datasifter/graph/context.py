from __future__ import annotations

from dataclasses import dataclass

from datasifter.graph.progress import AttributeState, ProgressTracker
from datasifter.graph.status import StatusEmitter
from datasifter.interfaces import (
    AttributeStore,
    JobRepository,
    MapEngine,
    RetrievalProvider,
)
from datasifter.schemas import ExtractionRequest, JobState, JobStatus, RetrievalConfig


class ExtractionCancelledError(Exception):
    """Raised when an extraction job is canceled by the backend."""


@dataclass
class ExtractionContext:
    request: ExtractionRequest
    job: JobState
    retrieval_config: RetrievalConfig
    retriever: RetrievalProvider
    map_engine: MapEngine
    attribute_store: AttributeStore
    job_repository: JobRepository
    emitter: StatusEmitter
    progress: ProgressTracker
    attribute_states: dict[str, AttributeState]

    async def ensure_active(self) -> None:
        refreshed = await self.job_repository.refresh(self.job)
        self.job = refreshed
        if refreshed.status == JobStatus.CANCELED:
            raise ExtractionCancelledError()


def build_extraction_context(
    *,
    request: ExtractionRequest,
    job: JobState,
    retrieval_config: RetrievalConfig,
    retriever: RetrievalProvider,
    map_engine: MapEngine,
    attribute_store: AttributeStore,
    job_repository: JobRepository,
    progress: ProgressTracker,
    attribute_states: dict[str, AttributeState],
    emitter: StatusEmitter,
) -> ExtractionContext:
    return ExtractionContext(
        request=request,
        job=job,
        retrieval_config=retrieval_config,
        retriever=retriever,
        map_engine=map_engine,
        attribute_store=attribute_store,
        job_repository=job_repository,
        emitter=emitter,
        progress=progress,
        attribute_states=attribute_states,
    )


__all__ = ["ExtractionCancelledError", "ExtractionContext", "build_extraction_context"]

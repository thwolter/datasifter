from __future__ import annotations

import pytest

from datasifter.interfaces import JobRepository
from datasifter.registry.registry import UnknownAttributeError
from datasifter.runner import ExtractionRunner
from datasifter.schemas import JobStatus, RetrievedChunk, StatusEvent

from tests.fixtures.factories import make_request
from tests.fixtures.fakes import (
    FakeJobRepository,
    FakeMapEngine,
    FakeRetrievalProvider,
)


def _map_engine_factory(engine: FakeMapEngine):
    def factory(_: str) -> FakeMapEngine:
        return engine

    return factory


@pytest.mark.asyncio
async def test_runner_returns_immediately_when_job_canceled(
    runner_defaults, job_state, attribute_store
) -> None:
    job_state.status = JobStatus.CANCELED
    job_state.error = "user canceled"
    job_repository: JobRepository = FakeJobRepository(job_state)

    def _never_called(*_args, **_kwargs):
        raise AssertionError("spec_resolver should not be invoked for canceled jobs")

    runner = ExtractionRunner(
        job_repository=job_repository,
        attribute_store=attribute_store,
        retrieval_provider=FakeRetrievalProvider([]),
        map_engine_factory=_map_engine_factory(FakeMapEngine()),
        defaults=runner_defaults,
        spec_resolver=_never_called,
    )

    outcome = await runner.run(make_request(), job=job_state)

    assert outcome.attributes == {}
    assert outcome.result.errors == ["user canceled"]
    assert job_repository.status_updates == []


@pytest.mark.asyncio
async def test_runner_handles_unknown_attributes_gracefully(
    runner_defaults, job_state, attribute_store
) -> None:
    job_repository = FakeJobRepository(job_state)

    def spec_resolver(*_args, **_kwargs):
        raise UnknownAttributeError("amount_due")

    runner = ExtractionRunner(
        job_repository=job_repository,
        attribute_store=attribute_store,
        retrieval_provider=FakeRetrievalProvider([]),
        map_engine_factory=_map_engine_factory(FakeMapEngine()),
        defaults=runner_defaults,
        spec_resolver=spec_resolver,
    )

    outcome = await runner.run(make_request(), job=job_state)

    assert outcome.attributes == {}
    assert "Unknown attribute" in outcome.result.errors[0]
    assert job_repository.status_updates == []


@pytest.mark.asyncio
async def test_runner_persists_results_and_emits_completion(
    runner_defaults,
    job_state,
    sample_spec,
    attribute_store,
    progress_sink,
) -> None:
    chunks = [
        RetrievedChunk(chunk_id="chunk-1", text="Total is 120", retr_score=0.8),
        RetrievedChunk(chunk_id="chunk-2", text="Fallback", retr_score=0.2),
    ]
    retriever = FakeRetrievalProvider(chunks)
    map_engine = FakeMapEngine(value="120", confidence=0.95)
    job_repository = FakeJobRepository(job_state)

    runner = ExtractionRunner(
        job_repository=job_repository,
        attribute_store=attribute_store,
        retrieval_provider=retriever,
        map_engine_factory=_map_engine_factory(map_engine),
        defaults=runner_defaults,
        progress_sink=progress_sink,
        spec_resolver=lambda *_: [sample_spec],
    )

    outcome = await runner.run(make_request(), job=job_state)

    assert outcome.result.errors == []
    assert outcome.attributes["total_due"].value == "120"
    assert attribute_store.persisted, "AttributeStore.persist should be called"
    assert (JobStatus.COMPLETED, None) in job_repository.status_updates
    assert progress_sink.published[-1].event == StatusEvent.JOB_COMPLETED


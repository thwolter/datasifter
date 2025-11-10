from __future__ import annotations

import pytest

from datasifter.registry import registry as registry_module
from datasifter.runner import ExtractionRunner
from datasifter.schemas import (
    AttributeType,
    Candidate,
    JobStatus,
    RetrievedChunk,
    RetrievalMetadata,
    Thresholds,
    StatusEvent,
)

from .fixtures.factories import make_attribute_spec, make_request
from .fixtures.fakes import (
    FakeAttributeStore,
    FakeJobRepository,
    FakeMapEngine,
    FakeProgressSink,
    FakeRetrievalProvider,
)


class AttributeAwareRetrievalProvider:
    def __init__(self, mapping: dict[str, list[RetrievedChunk]]) -> None:
        self._mapping = mapping
        self.calls: list[str] = []

    async def retrieve(self, *, job, request, attribute, config):
        chunks = self._mapping.get(attribute.name, [])
        self.calls.append(attribute.name)
        return list(chunks)


class AttributeAwareMapEngine:
    def __init__(self, outputs: dict[str, tuple[str, float]]) -> None:
        self._outputs = outputs
        self.calls: list[str] = []

    async def extract_candidate(
        self, *, doc_type, attribute, chunk, attempt, prompt_id=None
    ) -> Candidate:
        value, confidence = self._outputs[attribute.name]
        metadata = RetrievalMetadata(
            chunk_id=chunk.chunk_id,
            header=chunk.header,
            page=chunk.page,
            retr_score=chunk.retr_score,
            text_excerpt=chunk.text,
        )
        candidate = Candidate(
            attribute=attribute.name,
            value=value,
            confidence_local=confidence,
            rationale=f"{attribute.name}:{attempt}",
            retrieval=metadata,
            raw_json={"doc_type": doc_type},
        )
        self.calls.append(attribute.name)
        return candidate


class CancelOnRefreshJobRepository(FakeJobRepository):
    def __init__(self, job, *, cancel_after: int = 1) -> None:
        super().__init__(job)
        self._cancel_after = cancel_after

    async def refresh(self, job):
        self.refresh_calls += 1
        if self.refresh_calls >= self._cancel_after:
            self.job.status = JobStatus.CANCELED
            self.job.error = "canceled by user"
        return self.job


@pytest.mark.asyncio
async def test_runner_end_to_end_with_mixed_attribute_results(
    runner_defaults,
    job_state,
    attribute_store,
    progress_sink,
) -> None:
    total_spec = make_attribute_spec(
        name="total_due",
        attr_type=AttributeType.STRING,
        thresholds=Thresholds(min_confidence=0.6, min_chunks=1),
    )
    due_spec = make_attribute_spec(
        name="due_date",
        attr_type=AttributeType.DATE,
        thresholds=Thresholds(min_confidence=0.6, min_chunks=2),
    )
    registry_module.register("invoice", [total_spec, due_spec])

    retrieval = AttributeAwareRetrievalProvider(
        {
            "total_due": [
                RetrievedChunk(chunk_id="chunk-a", text="Amount: 120", retr_score=0.9),
                RetrievedChunk(chunk_id="chunk-b", text="Fallback 100", retr_score=0.7),
            ],
            "due_date": [
                RetrievedChunk(chunk_id="chunk-c", text="Due Jan 01", retr_score=0.8)
            ],
        }
    )
    map_engine_outputs = {
        "total_due": ("120", 0.95),
        "due_date": ("2024-01-01", 0.95),
    }

    def map_engine_factory(_model: str):
        return AttributeAwareMapEngine(map_engine_outputs)

    job_repository = FakeJobRepository(job_state)

    runner = ExtractionRunner(
        job_repository=job_repository,
        attribute_store=attribute_store,
        retrieval_provider=retrieval,
        map_engine_factory=map_engine_factory,
        defaults=runner_defaults,
        progress_sink=progress_sink,
    )

    request = make_request(doc_type="invoice")
    outcome = await runner.run(request, job=job_state)

    assert outcome.result.errors == []
    assert outcome.attributes["total_due"].status == "accepted"
    assert outcome.attributes["due_date"].status == "abstained"
    assert len(attribute_store.persisted) == 1
    assert attribute_store.persisted[0][1].name == "total_due"
    assert (JobStatus.COMPLETED, None) in job_repository.status_updates
    assert progress_sink.published[-1].event == StatusEvent.JOB_COMPLETED


@pytest.mark.asyncio
async def test_runner_honors_cancel_signal_during_processing(
    runner_defaults,
    job_state,
    attribute_store,
    progress_sink,
) -> None:
    spec = make_attribute_spec(
        name="total_due",
        attr_type=AttributeType.STRING,
        thresholds=Thresholds(min_confidence=0.1, min_chunks=1),
    )
    registry_module.register("invoice", [spec])

    retriever = FakeRetrievalProvider(
        [RetrievedChunk(chunk_id="chunk-1", text="Amount 50", retr_score=0.7)]
    )
    map_engine_factory = lambda _model: FakeMapEngine(value="50", confidence=0.8)
    job_repository = CancelOnRefreshJobRepository(job_state, cancel_after=1)

    runner = ExtractionRunner(
        job_repository=job_repository,
        attribute_store=attribute_store,
        retrieval_provider=retriever,
        map_engine_factory=map_engine_factory,
        defaults=runner_defaults,
        progress_sink=progress_sink,
    )

    request = make_request(doc_type="invoice")
    outcome = await runner.run(request, job=job_state)

    assert outcome.result.errors == ["canceled by user"]
    assert job_repository.status_updates[-1][0] == JobStatus.CANCELED
    assert attribute_store.persisted == []
    assert progress_sink.published[-1].event == StatusEvent.JOB_CANCELED

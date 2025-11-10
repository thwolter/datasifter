from __future__ import annotations

import pytest

from datasifter.graph.context import build_extraction_context
from datasifter.graph.phases import retrieve_attribute_chunks, threshold_and_persist
from datasifter.graph.progress import AttributeState, ProgressTracker
from datasifter.graph.status import StatusEmitter
from datasifter.schemas import (
    AttributeResult,
    Candidate,
    RetrievedChunk,
    RetrievalConfig,
    RetrievalMetadata,
    Thresholds,
)

from .fixtures.factories import make_request
from .fixtures.fakes import (
    FakeAttributeStore,
    FakeJobRepository,
    FakeMapEngine,
    FakeProgressSink,
    FakeRetrievalProvider,
)


def _make_context(
    job_state,
    request,
    retrieval_config,
    retriever,
    attribute_store,
    map_engine,
    attribute_states,
    progress,
    progress_sink,
):
    job_repository = FakeJobRepository(job_state)
    emitter = StatusEmitter(
        job=job_state,
        job_repository=job_repository,
        progress=progress,
        attribute_states=attribute_states,
        sink=progress_sink,
    )
    context = build_extraction_context(
        request=request,
        job=job_state,
        retrieval_config=retrieval_config,
        retriever=retriever,
        map_engine=map_engine,
        attribute_store=attribute_store,
        job_repository=job_repository,
        progress=progress,
        attribute_states=attribute_states,
        emitter=emitter,
    )
    return context


@pytest.mark.asyncio
async def test_retrieve_attribute_chunks_respects_top_m(job_state, sample_spec):
    request = make_request()
    attr_state = AttributeState(sample_spec.name)
    attribute_states = {sample_spec.name: attr_state}
    progress = ProgressTracker(total_attributes=1)
    retrieval_config = RetrievalConfig(max_chunks=5, top_m=1)
    retriever = FakeRetrievalProvider(
        [
            RetrievedChunk(chunk_id="chunk-1", text="first", retr_score=0.8),
            RetrievedChunk(chunk_id="chunk-2", text="second", retr_score=0.6),
        ]
    )
    context = _make_context(
        job_state,
        request,
        retrieval_config,
        retriever,
        FakeAttributeStore(),
        FakeMapEngine(),
        attribute_states,
        progress,
        FakeProgressSink(),
    )

    map_chunks = await retrieve_attribute_chunks(context, sample_spec, attr_state)

    assert [chunk.chunk_id for chunk in map_chunks] == ["chunk-1"]
    assert attr_state.planned == 1
    assert progress.map_calls_planned == 1


@pytest.mark.asyncio
async def test_threshold_and_persist_persists_when_thresholds_pass(
    job_state, sample_spec
):
    request = make_request()
    attr_state = AttributeState(sample_spec.name)
    attribute_states = {sample_spec.name: attr_state}
    progress = ProgressTracker(total_attributes=1)
    attribute_store = FakeAttributeStore()
    context = _make_context(
        job_state,
        request,
        RetrievalConfig(),
        FakeRetrievalProvider([]),
        attribute_store,
        FakeMapEngine(),
        attribute_states,
        progress,
        FakeProgressSink(),
    )
    validated = AttributeResult(
        name=sample_spec.name,
        value="120",
        confidence=0.95,
        provenance=("chunk-1",),
        chunk_count=2,
        status="accepted",
    )
    candidates = [
        Candidate(
            attribute=sample_spec.name,
            value="120",
            confidence_local=0.95,
            rationale="primary",
            retrieval=RetrievalMetadata(chunk_id="chunk-1"),
        )
    ]

    result = await threshold_and_persist(
        context,
        sample_spec,
        validated,
        candidates,
        len(candidates),
        attr_state,
    )

    assert result is validated
    assert attribute_store.persisted
    assert progress.persisted == 1
    assert progress.attributes_done == 1
    assert attr_state.state == "persisted"
    assert attr_state.confidence == validated.confidence


@pytest.mark.asyncio
async def test_threshold_and_persist_abstains_when_thresholds_fail(job_state, sample_spec):
    strict_spec = sample_spec.model_copy(
        update={"thresholds": Thresholds(min_confidence=0.99, min_chunks=3)}
    )
    request = make_request()
    attr_state = AttributeState(strict_spec.name)
    attribute_states = {strict_spec.name: attr_state}
    progress = ProgressTracker(total_attributes=1)
    attribute_store = FakeAttributeStore()
    context = _make_context(
        job_state,
        request,
        RetrievalConfig(),
        FakeRetrievalProvider([]),
        attribute_store,
        FakeMapEngine(),
        attribute_states,
        progress,
        FakeProgressSink(),
    )
    validated = AttributeResult(
        name=strict_spec.name,
        value="50",
        confidence=0.5,
        provenance=("chunk-1",),
        chunk_count=1,
        status="accepted",
    )
    candidates = [
        Candidate(
            attribute=strict_spec.name,
            value="50",
            confidence_local=0.5,
            rationale="low confidence",
            retrieval=RetrievalMetadata(chunk_id="chunk-1"),
        )
    ]

    result = await threshold_and_persist(
        context,
        strict_spec,
        validated,
        candidates,
        len(candidates),
        attr_state,
    )

    assert result.status == "abstained"
    assert result.value is None
    assert attribute_store.persisted == []
    assert progress.persisted == 0
    assert progress.attributes_done == 1
    assert attr_state.state == "abstained"


from __future__ import annotations

import pytest

from datasifter.graph.context import build_extraction_context
from datasifter.graph.pipeline import build_default_graph
from datasifter.graph.progress import AttributeState, ProgressTracker
from datasifter.graph.status import StatusEmitter
from datasifter.schemas import RetrievedChunk, RetrievalConfig

from tests.fixtures.factories import make_request
from tests.fixtures.fakes import (
    FakeAttributeStore,
    FakeJobRepository,
    FakeMapEngine,
    FakeProgressSink,
    FakeRetrievalProvider,
)


def _make_context(job_state, spec, retriever, attribute_store, map_engine):
    request = make_request(doc_type=job_state.doc_type, attributes=[spec.name])
    retrieval_config = RetrievalConfig(max_chunks=5, top_m=5)
    attribute_states = {spec.name: AttributeState(spec.name)}
    progress = ProgressTracker(total_attributes=1)
    job_repository = FakeJobRepository(job_state)
    emitter = StatusEmitter(
        job=job_state,
        job_repository=job_repository,
        progress=progress,
        attribute_states=attribute_states,
        sink=FakeProgressSink(),
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
async def test_graph_stage_override_controls_chunking(
    sample_spec,
    job_state,
) -> None:
    attribute_store = FakeAttributeStore()
    retriever = FakeRetrievalProvider(
        [
            RetrievedChunk(chunk_id="chunk-1", text="first", retr_score=0.8),
            RetrievedChunk(chunk_id="chunk-2", text="second", retr_score=0.6),
        ]
    )
    map_engine = FakeMapEngine()
    context = _make_context(job_state, sample_spec, retriever, attribute_store, map_engine)
    attr_state = context.attribute_states[sample_spec.name]
    attr_state.state = "mapping"

    async def _prefer_last_chunk(context, spec, attr_state, state):
        del spec  # chunk selection does not depend on spec metadata in this test
        state.chunked_chunks = state.ingested_chunks[-1:]
        attr_state.planned = len(state.chunked_chunks)
        context.progress.map_calls_planned += len(state.chunked_chunks)

    graph = build_default_graph().with_stage("chunking", _prefer_last_chunk)

    result = await graph.run_attribute(context, sample_spec)

    assert result.value == "second"
    assert len(attribute_store.persisted) == 1
    assert attribute_store.persisted[0][2].value == "second"
    assert attr_state.planned == 1

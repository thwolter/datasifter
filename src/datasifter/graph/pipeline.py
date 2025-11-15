from __future__ import annotations

from dataclasses import dataclass, field
from typing import Awaitable, Callable, Sequence

from datasifter.graph.chunking import plan_chunks
from datasifter.graph.context import ExtractionContext
from datasifter.graph.embedding import run_embedding
from datasifter.graph.enrichment import reduce_attribute, validate_attribute
from datasifter.graph.ingestion import run_ingestion
from datasifter.graph.persistence import persist_attribute
from datasifter.graph.progress import AttributeState
from datasifter.schemas import (
    AttributeResult,
    AttributeSpec,
    Candidate,
    ReduceAggregate,
    RetrievedChunk,
)

StageCallable = Callable[
    [ExtractionContext, AttributeSpec, AttributeState, "AttributePipelineState"],
    Awaitable[None],
]


@dataclass
class AttributePipelineState:
    ingested_chunks: list[RetrievedChunk] = field(default_factory=list)
    chunked_chunks: list[RetrievedChunk] = field(default_factory=list)
    candidates: list[Candidate] = field(default_factory=list)
    aggregate: ReduceAggregate | None = None
    validated: AttributeResult | None = None
    result: AttributeResult | None = None

    @property
    def chunk_count(self) -> int:
        return len(self.chunked_chunks)


@dataclass
class GraphStage:
    name: str
    handler: StageCallable


class AttributeExtractionGraph:
    """Minimal DAG runner that mirrors the Metis extraction orchestration graph."""

    def __init__(self, stages: Sequence[GraphStage] | None = None) -> None:
        self._stages = list(stages or [])
        self._index = {stage.name: idx for idx, stage in enumerate(self._stages)}

    def with_stage(self, name: str, handler: StageCallable) -> "AttributeExtractionGraph":
        if name not in self._index:
            msg = f"Unknown stage {name!r}"
            raise KeyError(msg)
        new_stages = list(self._stages)
        new_stages[self._index[name]] = GraphStage(name=name, handler=handler)
        return AttributeExtractionGraph(new_stages)

    def insert_stage(
        self,
        stage: GraphStage,
        *,
        before: str | None = None,
        after: str | None = None,
    ) -> "AttributeExtractionGraph":
        new_stages = list(self._stages)
        index = len(new_stages)
        if before is not None and before in self._index:
            index = self._index[before]
        elif after is not None and after in self._index:
            index = self._index[after] + 1
        new_stages.insert(index, stage)
        return AttributeExtractionGraph(new_stages)

    async def run_attribute(
        self,
        context: ExtractionContext,
        spec: AttributeSpec,
    ) -> AttributeResult:
        attr_state = context.attribute_states[spec.name]
        state = AttributePipelineState()
        for stage in self._stages:
            await stage.handler(context, spec, attr_state, state)
        if state.result is None:
            msg = f"Pipeline for {spec.name!r} did not produce a result"
            raise RuntimeError(msg)
        return state.result


async def _ingestion_stage(
    context: ExtractionContext,
    spec: AttributeSpec,
    attr_state: AttributeState,
    state: AttributePipelineState,
) -> None:
    state.ingested_chunks = await run_ingestion(context, spec, attr_state)
    if not state.chunked_chunks:
        state.chunked_chunks = list(state.ingested_chunks)


async def _chunking_stage(
    context: ExtractionContext,
    spec: AttributeSpec,
    attr_state: AttributeState,
    state: AttributePipelineState,
) -> None:
    state.chunked_chunks = plan_chunks(
        context,
        spec,
        state.ingested_chunks or state.chunked_chunks,
        attr_state,
    )


async def _embedding_stage(
    context: ExtractionContext,
    spec: AttributeSpec,
    attr_state: AttributeState,
    state: AttributePipelineState,
) -> None:
    state.candidates = await run_embedding(
        context,
        spec,
        state.chunked_chunks,
        attr_state,
    )


async def _enrichment_stage(
    context: ExtractionContext,
    spec: AttributeSpec,
    attr_state: AttributeState,
    state: AttributePipelineState,
) -> None:
    state.aggregate = await reduce_attribute(
        context,
        spec,
        state.candidates,
        attr_state,
    )
    state.validated = await validate_attribute(
        context,
        spec,
        state.aggregate,
        state.chunk_count,
        attr_state,
    )


async def _persistence_stage(
    context: ExtractionContext,
    spec: AttributeSpec,
    attr_state: AttributeState,
    state: AttributePipelineState,
) -> None:
    if state.validated is None:
        msg = f"Attribute {spec.name!r} missing validated payload before persistence"
        raise RuntimeError(msg)
    state.result = await persist_attribute(
        context,
        spec,
        state.validated,
        state.candidates,
        state.chunk_count,
        attr_state,
    )


def build_default_graph() -> AttributeExtractionGraph:
    """Return the default Metis-style runner graph."""

    return AttributeExtractionGraph(
        [
            GraphStage("ingestion", _ingestion_stage),
            GraphStage("chunking", _chunking_stage),
            GraphStage("embedding", _embedding_stage),
            GraphStage("enrichment", _enrichment_stage),
            GraphStage("persistence", _persistence_stage),
        ]
    )


__all__ = [
    "AttributeExtractionGraph",
    "AttributePipelineState",
    "GraphStage",
    "build_default_graph",
]

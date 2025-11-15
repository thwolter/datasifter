from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from datasifter.graph.chunking import plan_chunks
from datasifter.graph.context import ExtractionContext
from datasifter.graph.embedding import run_embedding
from datasifter.graph.enrichment import (
    reduce_attribute as _reduce_attribute,
    validate_attribute as _validate_attribute,
)
from datasifter.graph.ingestion import run_ingestion
from datasifter.graph.persistence import persist_attribute
from datasifter.graph.progress import AttributeState
from datasifter.schemas import AttributeResult, AttributeSpec, Candidate, RetrievedChunk


async def retrieve_attribute_chunks(
    context: ExtractionContext,
    spec: AttributeSpec,
    attr_state: AttributeState,
) -> list[RetrievedChunk]:
    ingested = await run_ingestion(context, spec, attr_state)
    return plan_chunks(context, spec, ingested, attr_state)


async def map_attribute_chunks(
    context: ExtractionContext,
    spec: AttributeSpec,
    map_chunks: Sequence[RetrievedChunk],
    attr_state: AttributeState,
) -> list[Candidate]:
    return await run_embedding(context, spec, map_chunks, attr_state)


async def reduce_attribute(
    context: ExtractionContext,
    spec: AttributeSpec,
    candidates: Sequence[Candidate],
    attr_state: AttributeState,
) -> Any:
    return await _reduce_attribute(context, spec, candidates, attr_state)


async def validate_attribute(
    context: ExtractionContext,
    spec: AttributeSpec,
    aggregate: Any,
    chunk_count: int,
    attr_state: AttributeState,
) -> AttributeResult:
    return await _validate_attribute(
        context,
        spec,
        aggregate,
        chunk_count,
        attr_state,
    )


async def threshold_and_persist(
    context: ExtractionContext,
    spec: AttributeSpec,
    validated: AttributeResult,
    candidates: Sequence[Candidate],
    chunk_count: int,
    attr_state: AttributeState,
) -> AttributeResult:
    return await persist_attribute(
        context,
        spec,
        validated,
        candidates,
        chunk_count,
        attr_state,
    )


__all__ = [
    "retrieve_attribute_chunks",
    "map_attribute_chunks",
    "reduce_attribute",
    "validate_attribute",
    "threshold_and_persist",
]

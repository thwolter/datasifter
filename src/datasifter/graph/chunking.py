from __future__ import annotations

from datasifter.graph.context import ExtractionContext
from datasifter.graph.progress import AttributeState
from datasifter.schemas import AttributeSpec, RetrievedChunk


def plan_chunks(
    context: ExtractionContext,
    spec: AttributeSpec,
    ingested_chunks: list[RetrievedChunk],
    attr_state: AttributeState,
) -> list[RetrievedChunk]:
    """Limit retrieved chunks to top-m map calls while updating progress trackers."""

    del spec  # Reserved for heuristics (regex hints, chunk scoring, etc.).
    if (
        context.retrieval_config.top_m
        and context.retrieval_config.top_m < len(ingested_chunks)
    ):
        planned = list(ingested_chunks[: context.retrieval_config.top_m])
    else:
        planned = list(ingested_chunks)

    attr_state.planned = len(planned)
    context.progress.map_calls_planned += len(planned)
    return planned


__all__ = ["plan_chunks"]

from __future__ import annotations

from datasifter.graph.context import ExtractionContext
from datasifter.graph.progress import AttributeState
from datasifter.schemas import AttributeSpec, RetrievedChunk


async def run_ingestion(
    context: ExtractionContext,
    spec: AttributeSpec,
    attr_state: AttributeState,
) -> list[RetrievedChunk]:
    """Fetch raw retrieval chunks using the active RetrievalProvider."""

    del attr_state  # Reserved for future heuristics.
    await context.ensure_active()
    chunks = await context.retriever.retrieve(
        job=context.job,
        request=context.request,
        attribute=spec,
        config=context.retrieval_config,
    )
    return list(chunks)


__all__ = ["run_ingestion"]

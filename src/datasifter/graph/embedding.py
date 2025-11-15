from __future__ import annotations

from collections.abc import Sequence

from datasifter.graph.context import ExtractionContext
from datasifter.graph.progress import AttributeState
from datasifter.schemas import AttributeSpec, Candidate, RetrievedChunk, StatusEvent


async def run_embedding(
    context: ExtractionContext,
    spec: AttributeSpec,
    map_chunks: Sequence[RetrievedChunk],
    attr_state: AttributeState,
) -> list[Candidate]:
    """Invoke the MapEngine over each chunk and emit progress events."""

    candidates: list[Candidate] = []
    for chunk in map_chunks:
        await context.ensure_active()
        candidate = await context.map_engine.extract_candidate(
            doc_type=context.request.doc_type,
            attribute=spec,
            chunk=chunk,
            attempt=len(candidates) + 1,
        )
        candidates.append(candidate)
        attr_state.mapped += 1
        context.progress.map_calls_done += 1
        await context.emitter.emit(
            StatusEvent.CHUNK_MAPPED,
            attribute_payload={
                "name": spec.name,
                "phase": "map",
                "retrieval": candidate.retrieval.model_dump(mode="json"),
                "candidate": {
                    "value": candidate.value,
                    "confidence_local": candidate.confidence_local,
                    "rationale": candidate.rationale,
                },
            },
        )
    return candidates


__all__ = ["run_embedding"]

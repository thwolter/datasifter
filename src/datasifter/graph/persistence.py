from __future__ import annotations

from collections.abc import Sequence

from datasifter.graph.context import ExtractionContext
from datasifter.graph.progress import AttributeState
from datasifter.schemas import AttributeResult, AttributeSpec, Candidate, StatusEvent, Thresholds
from datasifter.thresholds import abstain_output, passes_thresholds


def _default_thresholds() -> Thresholds:
    return Thresholds(min_confidence=0.65, min_chunks=1)


async def persist_attribute(
    context: ExtractionContext,
    spec: AttributeSpec,
    validated: AttributeResult,
    candidates: Sequence[Candidate],
    chunk_count: int,
    attr_state: AttributeState,
) -> AttributeResult:
    thresholds = spec.thresholds or _default_thresholds()
    passes = passes_thresholds(validated, thresholds, chunk_count)
    attr_state.state = "thresholded"
    decision = "accept" if passes else "abstain"
    await context.ensure_active()
    await context.emitter.emit(
        StatusEvent.ATTRIBUTE_THRESHOLDED,
        attribute_payload={
            "name": spec.name,
            "phase": "threshold",
            "decision": decision,
            "thresholds": thresholds.model_dump(),
        },
    )

    if not passes or context.request.dry_run:
        result = abstain_output(spec.name, candidates)
        attr_state.state = "abstained" if not passes else "persisted"
        context.progress.attributes_done += 1
        await context.ensure_active()
        await context.emitter.emit(
            StatusEvent.ATTRIBUTE_PERSISTED,
            attribute_payload={
                "name": spec.name,
                "phase": "persist",
                "value": result.value,
                "confidence": result.confidence,
                "status": result.status,
            },
            include_snapshot=True,
        )
        return result

    await context.attribute_store.persist(context.job, spec, validated)
    context.progress.persisted += 1
    context.progress.attributes_done += 1
    attr_state.state = "persisted"
    attr_state.confidence = validated.confidence
    await context.ensure_active()
    await context.emitter.emit(
        StatusEvent.ATTRIBUTE_PERSISTED,
        attribute_payload={
            "name": spec.name,
            "phase": "persist",
            "value": validated.value,
            "confidence": validated.confidence,
            "status": validated.status,
        },
        include_snapshot=True,
    )
    return validated


__all__ = ["persist_attribute"]

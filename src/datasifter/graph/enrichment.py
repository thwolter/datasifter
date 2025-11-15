from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from datasifter.graph.context import ExtractionContext
from datasifter.graph.progress import AttributeState
from datasifter.schemas import (
    AttributeResult,
    AttributeSpec,
    Candidate,
    ReduceAggregate,
    StatusEvent,
)
from datasifter.tools import apply_validation, reduce_candidates


async def reduce_attribute(
    context: ExtractionContext,
    spec: AttributeSpec,
    candidates: Sequence[Candidate],
    attr_state: AttributeState,
) -> ReduceAggregate:
    aggregate = reduce_candidates(candidates)
    context.progress.reduce_done += 1
    attr_state.state = "reduced"
    attr_state.confidence = aggregate.confidence
    await context.ensure_active()
    await context.emitter.emit(
        StatusEvent.ATTRIBUTE_REDUCED,
        attribute_payload={
            "name": spec.name,
            "phase": "reduce",
            "aggregate": {
                "value": aggregate.value,
                "confidence": aggregate.confidence,
                "provenance": list(aggregate.provenance),
                "supporting": [
                    cand.raw_json for cand in aggregate.supporting_candidates
                ],
            },
        },
    )
    return aggregate


async def validate_attribute(
    context: ExtractionContext,
    spec: AttributeSpec,
    aggregate: Any,
    chunk_count: int,
    attr_state: AttributeState,
) -> AttributeResult:
    validated = apply_validation(
        attribute=spec,
        value=aggregate.value,
        confidence=aggregate.confidence,
        chunk_count=chunk_count,
        provenance=aggregate.provenance,
    )
    context.progress.validated += 1
    attr_state.state = "validated"
    attr_state.confidence = validated.confidence

    await context.ensure_active()
    await context.emitter.emit(
        StatusEvent.ATTRIBUTE_VALIDATED,
        attribute_payload={
            "name": spec.name,
            "phase": "validate",
            "value": validated.value,
            "issues": [issue.model_dump() for issue in validated.validation_issues],
        },
    )
    return validated


async def enrich_attribute(
    context: ExtractionContext,
    spec: AttributeSpec,
    candidates: Sequence[Candidate],
    attr_state: AttributeState,
) -> tuple[ReduceAggregate, AttributeResult]:
    aggregate = await reduce_attribute(context, spec, candidates, attr_state)
    validated = await validate_attribute(
        context,
        spec,
        aggregate,
        len(candidates),
        attr_state,
    )
    return aggregate, validated


__all__ = ["reduce_attribute", "validate_attribute", "enrich_attribute"]

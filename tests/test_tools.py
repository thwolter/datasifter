from __future__ import annotations

from datasifter.schemas import (
    AttributeConstraints,
    AttributeResult,
    AttributeSpec,
    AttributeType,
    Candidate,
    RetrievalMetadata,
    Thresholds,
)
from datasifter.thresholds import abstain_output, passes_thresholds
from datasifter.tools import apply_validation, reduce_candidates


def _candidate(
    *,
    value: str,
    chunk_id: str,
    confidence: float,
    retr_score: float,
) -> Candidate:
    return Candidate(
        attribute="supplier",
        value=value,
        confidence_local=confidence,
        rationale="",
        retrieval=RetrievalMetadata(
            chunk_id=chunk_id, retr_score=retr_score, text_excerpt=value
        ),
    )


def test_reduce_candidates_groups_equivalent_values():
    candidates = [
        _candidate(value="ACME Inc", chunk_id="c1", confidence=0.8, retr_score=0.6),
        _candidate(value="acme inc ", chunk_id="c2", confidence=0.6, retr_score=0.9),
        _candidate(value="Globex", chunk_id="c3", confidence=0.95, retr_score=0.5),
    ]

    aggregate = reduce_candidates(candidates)

    assert aggregate.value == "ACME Inc"
    assert aggregate.provenance == ("c1", "c2")
    assert len(aggregate.supporting_candidates) == 2
    assert aggregate.confidence > 0.6


def test_apply_validation_normalises_and_flags_range_issues():
    spec = AttributeSpec(
        name="employee_count",
        type=AttributeType.INTEGER,
        description="Number of employees",
        constraints=AttributeConstraints(min_value=10, max_value=100),
    )

    accepted = apply_validation(
        attribute=spec,
        value=" 42 ",
        confidence=0.9,
        chunk_count=3,
        provenance=("c1",),
    )
    assert accepted.value == 42
    assert accepted.status == "accepted"
    assert accepted.validation_issues == ()

    rejected = apply_validation(
        attribute=spec,
        value="5",
        confidence=0.9,
        chunk_count=1,
        provenance=("c2",),
    )
    assert rejected.status == "abstained"
    assert any(issue.code == "range" for issue in rejected.validation_issues)


def test_passes_thresholds_and_abstain_output_behaviour():
    thresholds = Thresholds(min_confidence=0.8, min_chunks=2)
    result = AttributeResult(
        name="total_due",
        value="100",
        confidence=0.85,
        provenance=("c1",),
        chunk_count=2,
        status="accepted",
    )

    assert passes_thresholds(result, thresholds, chunk_count=2)

    weak = result.model_copy(update={"confidence": 0.2})
    assert not passes_thresholds(weak, thresholds, chunk_count=2)

    insufficient_chunks = result.model_copy(update={"chunk_count": 1})
    assert not passes_thresholds(insufficient_chunks, thresholds, chunk_count=1)

    abstained = abstain_output(
        "total_due",
        [_candidate(value="?", chunk_id="c1", confidence=0.2, retr_score=0.1)],
    )
    assert abstained.status == "abstained"
    assert abstained.value is None
    assert abstained.provenance == ("c1",)

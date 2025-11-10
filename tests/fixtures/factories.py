from __future__ import annotations

from datetime import datetime
from typing import Sequence
from uuid import uuid4

from datasifter.schemas import (
    AttributeSpec,
    AttributeType,
    ExtractionRequest,
    JobState,
    JobStatus,
    RetrievalConfig,
    Thresholds,
)


def make_attribute_spec(
    *,
    name: str = "total_due",
    attr_type: AttributeType = AttributeType.STRING,
    description: str = "Total amount due",
    thresholds: Thresholds | None = None,
) -> AttributeSpec:
    data = {
        "name": name,
        "type": attr_type,
        "description": description,
    }
    if thresholds is not None:
        data["thresholds"] = thresholds
    return AttributeSpec(**data)


def make_retrieval_config(**overrides: int | float) -> RetrievalConfig:
    return RetrievalConfig(**overrides)


def make_request(
    *,
    doc_type: str = "invoice",
    attributes: Sequence[str] | None = None,
    dry_run: bool = False,
    model: str | None = None,
    retriever: RetrievalConfig | None = None,
) -> ExtractionRequest:
    return ExtractionRequest(
        doc_id=uuid4(),
        doc_type=doc_type,
        attributes=attributes,
        dry_run=dry_run,
        model=model,
        retriever=retriever,
    )


def make_job_state(
    *,
    status: JobStatus = JobStatus.RUNNING,
    doc_type: str = "invoice",
    model: str = "test-model",
    model_version: str = "1.0",
) -> JobState:
    started = datetime.utcnow()
    return JobState(
        job_id=uuid4(),
        doc_id=uuid4(),
        doc_type=doc_type,
        model=model,
        model_version=model_version,
        status=status,
        started_at=started,
    )


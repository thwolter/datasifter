from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from datasifter.adapters.postgres import (
    SqlModelAttributeStore,
    SqlModelJobRepository,
)
from datasifter.schemas import (
    AttributeResult,
    AttributeSpec,
    AttributeType,
    ExtractionRequest,
    JobState,
    JobStatus,
    RetrievalConfig,
    Thresholds,
)


class DummyJobModel:
    def __init__(
        self,
        *,
        tenant_id: UUID,
        doc_id: UUID,
        doc_type: str,
        model: str,
        model_version: str,
        document_digest: str,
        collection_name: str,
        retriever_config: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> None:
        self.job_id = uuid4()
        self.tenant_id = tenant_id
        self.doc_id = doc_id
        self.doc_type = doc_type
        self.model = model
        self.model_version = model_version
        self.document_digest = document_digest
        self.collection_name = collection_name
        self.status: str = JobStatus.QUEUED.value
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.error: str | None = None
        self.retriever_config = retriever_config
        self.options = options
        self.seq = 0


class DummySession:
    def __init__(self) -> None:
        self.jobs: dict[UUID, DummyJobModel] = {}
        self.persisted: list[tuple[UUID, AttributeResult]] = []

    async def get(self, model: type[Any], obj_id: UUID) -> DummyJobModel | None:
        del model
        return self.jobs.get(obj_id)

    def add(self, instance: DummyJobModel) -> None:
        self.jobs[instance.job_id] = instance

    async def flush(self) -> None:
        return None

    async def refresh(self, instance: DummyJobModel) -> None:
        del instance
        return None


async def create_job(
    session: DummySession,
    *,
    tenant_id: UUID,
    doc_id: UUID,
    doc_type: str,
    model: str,
    model_version: str,
    retriever_config: dict[str, Any] | None,
    options: dict[str, Any] | None,
    document_digest: str,
    collection_name: str,
) -> DummyJobModel:
    job = DummyJobModel(
        tenant_id=tenant_id,
        doc_id=doc_id,
        doc_type=doc_type,
        model=model,
        model_version=model_version,
        retriever_config=retriever_config,
        options=options,
        document_digest=document_digest,
        collection_name=collection_name,
    )
    session.add(job)
    return job


async def update_job_status(
    session: DummySession,
    job: DummyJobModel,
    status: str,
    error: str | None = None,
) -> DummyJobModel:
    job.status = status
    if status == JobStatus.RUNNING.value and job.started_at is None:
        job.started_at = datetime.utcnow()
    if status in {
        JobStatus.COMPLETED.value,
        JobStatus.CANCELED.value,
        JobStatus.FAILED.value,
    }:
        job.finished_at = datetime.utcnow()
    job.error = error
    session.add(job)
    return job


async def increment_sequence(session: DummySession, job: DummyJobModel) -> int:
    del session
    job.seq += 1
    return job.seq


async def persist_attribute(
    session: DummySession,
    *,
    tenant_id: UUID,
    job: DummyJobModel,
    result: AttributeResult,
    spec: AttributeSpec,
) -> None:
    del tenant_id, spec
    session.persisted.append((job.job_id, result))


def build_repo(session: DummySession) -> SqlModelJobRepository:
    return SqlModelJobRepository(
        session=session,
        job_model=DummyJobModel,
        status_factory=lambda status: status.value,
        create_job=create_job,
        update_job_status=update_job_status,
        increment_sequence=increment_sequence,
    )


def build_store(session: DummySession) -> SqlModelAttributeStore:
    return SqlModelAttributeStore(
        session=session,
        job_model=DummyJobModel,
        persist_attribute=persist_attribute,
    )


def make_request(
    *,
    tenant_id: UUID,
    doc_id: UUID,
    digest: str | None = "hash",
    collection_name: str | None = "vectra_docs",
) -> ExtractionRequest:
    return ExtractionRequest(
        tenant_id=tenant_id,
        doc_id=doc_id,
        doc_type="invoice",
        digest=digest,
        collection_name=collection_name,
    )


@pytest.mark.asyncio
async def test_prepare_job_creates_new_record() -> None:
    session = DummySession()
    repo = build_repo(session)
    request = make_request(tenant_id=uuid4(), doc_id=uuid4())
    retrieval = RetrievalConfig(max_chunks=5, top_m=2)
    job = await repo.prepare_job(
        request=request,
        job=None,
        retrieval_config=retrieval,
        model_name="gpt",
        model_version="2025",
    )
    assert job.status is JobStatus.RUNNING
    assert job.retriever_config == retrieval.model_dump(mode="json")
    assert job.context["orm"].job_id == job.job_id


@pytest.mark.asyncio
async def test_prepare_job_updates_existing_record() -> None:
    session = DummySession()
    repo = build_repo(session)
    tenant_id = uuid4()
    doc_id = uuid4()
    request = make_request(tenant_id=tenant_id, doc_id=doc_id)
    retrieval = RetrievalConfig()
    job = await repo.prepare_job(
        request=request,
        job=None,
        retrieval_config=retrieval,
        model_name="gpt-4o",
        model_version="2025-01-01",
    )
    updated_request = make_request(
        tenant_id=tenant_id, doc_id=doc_id, digest="updated", collection_name="alt"
    )
    job = await repo.prepare_job(
        request=updated_request,
        job=job,
        retrieval_config=retrieval,
        model_name="gpt-4o-mini",
        model_version="2025-02-01",
    )
    assert job.model == "gpt-4o-mini"
    assert job.document_digest == "updated"
    assert job.collection_name == "alt"


@pytest.mark.asyncio
async def test_prepare_job_missing_digest_raises() -> None:
    session = DummySession()
    repo = build_repo(session)
    request = make_request(tenant_id=uuid4(), doc_id=uuid4(), digest=None)
    retrieval = RetrievalConfig()
    with pytest.raises(ValueError):
        await repo.prepare_job(
            request=request,
            job=None,
            retrieval_config=retrieval,
            model_name="gpt",
            model_version="m1",
        )


@pytest.mark.asyncio
async def test_update_status_and_persist_attribute() -> None:
    session = DummySession()
    repo = build_repo(session)
    store = build_store(session)
    request = make_request(tenant_id=uuid4(), doc_id=uuid4())
    retrieval = RetrievalConfig()
    job = await repo.prepare_job(
        request=request,
        job=None,
        retrieval_config=retrieval,
        model_name="gpt",
        model_version="m1",
    )
    job = await repo.update_status(job, status=JobStatus.COMPLETED)
    assert job.status is JobStatus.COMPLETED
    spec = AttributeSpec(
        name="total",
        type=AttributeType.FLOAT,
        description="Invoice total",
        thresholds=Thresholds(min_confidence=0.5),
    )
    result = AttributeResult(name="total", value=123.45, confidence=0.9, provenance=())
    await store.persist(job, spec, result)
    assert session.persisted[0][0] == job.job_id
    assert session.persisted[0][1].value == 123.45


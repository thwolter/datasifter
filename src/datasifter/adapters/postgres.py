from __future__ import annotations

from typing import Any, Callable, Protocol, TypeVar
from uuid import UUID

from datasifter.interfaces import AttributeStore, JobRepository
from datasifter.schemas import (
    AttributeResult,
    AttributeSpec,
    ExtractionRequest,
    JobState,
    JobStatus,
    RetrievalConfig,
)


class AsyncSessionProtocol(Protocol):
    async def get(self, model: type[Any], obj_id: Any) -> Any | None: ...

    def add(self, instance: Any) -> None: ...

    async def flush(self) -> None: ...

    async def refresh(self, instance: Any) -> None: ...


class JobModelProtocol(Protocol):
    job_id: UUID
    doc_id: UUID
    doc_type: str
    model: str
    model_version: str
    status: Any
    tenant_id: UUID
    document_digest: str
    collection_name: str
    started_at: Any | None
    finished_at: Any | None
    error: str | None
    retriever_config: dict[str, Any] | None
    options: dict[str, Any] | None
    seq: int


ModelT = TypeVar("ModelT", bound=JobModelProtocol)
StatusT = TypeVar("StatusT")


class CreateJobFn(Protocol[ModelT]):
    async def __call__(
        self,
        session: AsyncSessionProtocol,
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
    ) -> ModelT: ...


class UpdateJobStatusFn(Protocol[ModelT, StatusT]):
    async def __call__(
        self,
        session: AsyncSessionProtocol,
        job: ModelT,
        status: StatusT,
        error: str | None = None,
    ) -> ModelT: ...


class IncrementSequenceFn(Protocol[ModelT]):
    async def __call__(self, session: AsyncSessionProtocol, job: ModelT) -> int: ...


class PersistAttributeFn(Protocol[ModelT]):
    async def __call__(
        self,
        session: AsyncSessionProtocol,
        *,
        tenant_id: UUID,
        job: ModelT,
        result: AttributeResult,
        spec: AttributeSpec,
    ) -> Any: ...


JobStateFactory = Callable[[ModelT, JobState | None], JobState]
TenantResolver = Callable[[ExtractionRequest, ModelT | None], UUID]
StatusFactory = Callable[[JobStatus], StatusT]
OptionsBuilder = Callable[[ExtractionRequest], dict[str, Any] | None]


def job_state_from_model(model: ModelT, *, base: JobState | None = None) -> JobState:
    payload = {
        "job_id": model.job_id,
        "doc_id": model.doc_id,
        "doc_type": model.doc_type,
        "model": model.model,
        "model_version": model.model_version,
        "status": JobStatus(getattr(model.status, "value", model.status)),
        "tenant_id": model.tenant_id,
        "document_digest": model.document_digest,
        "collection_name": model.collection_name,
        "started_at": model.started_at,
        "finished_at": model.finished_at,
        "error": model.error,
        "retriever_config": model.retriever_config,
        "options": model.options,
        "seq": model.seq,
    }
    if base is None:
        state = JobState(**payload)
    else:
        for key, value in payload.items():
            setattr(base, key, value)
        state = base
    state.context.setdefault("orm", model)
    state.context["orm"] = model
    return state


default_job_state_from_model = job_state_from_model


def default_tenant_resolver(
    request: ExtractionRequest, existing: JobModelProtocol | None
) -> UUID:
    if existing and existing.tenant_id:
        return existing.tenant_id
    if request.tenant_id is None:
        msg = "tenant_id must be provided when preparing extraction jobs"
        raise ValueError(msg)
    return request.tenant_id


def default_options_builder(request: ExtractionRequest) -> dict[str, Any]:
    return {"dry_run": request.dry_run}


class SqlModelJobRepository(JobRepository):
    def __init__(
        self,
        *,
        session: AsyncSessionProtocol,
        job_model: type[ModelT],
        status_factory: StatusFactory,
        create_job: CreateJobFn[ModelT],
        update_job_status: UpdateJobStatusFn[ModelT, StatusT],
        increment_sequence: IncrementSequenceFn[ModelT],
        job_state_factory: JobStateFactory = default_job_state_from_model,
        tenant_resolver: TenantResolver = default_tenant_resolver,
        options_builder: OptionsBuilder = default_options_builder,
    ) -> None:
        self._session = session
        self._job_model = job_model
        self._status_factory = status_factory
        self._create_job = create_job
        self._update_job_status = update_job_status
        self._increment_sequence = increment_sequence
        self._job_state_factory = job_state_factory
        self._tenant_resolver = tenant_resolver
        self._options_builder = options_builder

    async def prepare_job(
        self,
        *,
        request: ExtractionRequest,
        job: JobState | None,
        retrieval_config: RetrievalConfig,
        model_name: str,
        model_version: str,
    ) -> JobState:
        existing_model = (
            await _ensure_job_model(self._session, self._job_model, job)
            if job is not None
            else None
        )
        tenant_id = self._tenant_resolver(request, existing_model)
        retriever_snapshot = retrieval_config.model_dump(mode="json")
        options = self._options_builder(request)

        if existing_model is None:
            self._validate_new_job_request(request)
            new_job = await self._create_job(
                self._session,
                tenant_id=tenant_id,
                doc_id=request.doc_id,
                doc_type=request.doc_type,
                model=model_name,
                model_version=model_version,
                retriever_config=retriever_snapshot,
                options=options,
                document_digest=request.digest,  # type: ignore[arg-type]
                collection_name=request.collection_name,  # type: ignore[arg-type]
            )
            prepared = await self._update_job_status(
                self._session,
                new_job,
                self._coerce_status(JobStatus.RUNNING),
            )
            return self._job_state_factory(prepared)

        updated = existing_model
        if updated.model != model_name:
            updated.model = model_name
        if updated.model_version != model_version:
            updated.model_version = model_version
        updated.retriever_config = retriever_snapshot
        updated.options = options
        if request.digest is not None:
            updated.document_digest = request.digest
        if request.collection_name is not None:
            updated.collection_name = request.collection_name
        self._session.add(updated)
        await self._session.flush()
        await self._session.refresh(updated)
        prepared = await self._update_job_status(
            self._session,
            updated,
            self._coerce_status(JobStatus.RUNNING),
        )
        return self._job_state_factory(prepared, base=job)

    async def update_status(
        self,
        job: JobState,
        *,
        status: JobStatus,
        error: str | None = None,
    ) -> JobState:
        model = await _ensure_job_model(self._session, self._job_model, job)
        updated = await self._update_job_status(
            self._session, model, self._coerce_status(status), error
        )
        return self._job_state_factory(updated, base=job)

    async def refresh(self, job: JobState) -> JobState:
        model = await _ensure_job_model(self._session, self._job_model, job)
        await self._session.refresh(model)
        return self._job_state_factory(model, base=job)

    async def increment_sequence(self, job: JobState) -> int:
        model = await _ensure_job_model(self._session, self._job_model, job)
        seq = await self._increment_sequence(self._session, model)
        job.seq = seq
        return seq

    def _validate_new_job_request(self, request: ExtractionRequest) -> None:
        if request.digest is None or request.collection_name is None:
            msg = "digest and collection_name must be provided when creating a job"
            raise ValueError(msg)

    def _coerce_status(self, status: JobStatus) -> StatusT:
        coerced = self._status_factory(status)
        if coerced is None:
            msg = f"Unable to convert {status} to backend status"
            raise RuntimeError(msg)
        return coerced


class SqlModelAttributeStore(AttributeStore):
    def __init__(
        self,
        *,
        session: AsyncSessionProtocol,
        job_model: type[ModelT],
        persist_attribute: PersistAttributeFn[ModelT],
    ) -> None:
        self._session = session
        self._job_model = job_model
        self._persist_attribute = persist_attribute

    async def persist(
        self, job: JobState, spec: AttributeSpec, result: AttributeResult
    ) -> None:
        model = await _ensure_job_model(self._session, self._job_model, job)
        await self._persist_attribute(
            self._session,
            tenant_id=model.tenant_id,
            job=model,
            result=result,
            spec=spec,
        )


async def _ensure_job_model(
    session: AsyncSessionProtocol,
    job_model: type[ModelT],
    state: JobState,
) -> ModelT:
    model = state.context.get("orm")
    if isinstance(model, job_model):
        return model
    record = await session.get(job_model, state.job_id)
    if record is None:
        msg = f"Extraction job {state.job_id} not found"
        raise RuntimeError(msg)
    state.context["orm"] = record
    return record


__all__ = [
    "SqlModelJobRepository",
    "SqlModelAttributeStore",
    "job_state_from_model",
    "default_job_state_from_model",
    "default_tenant_resolver",
]

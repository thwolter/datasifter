from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence

from datasifter.graph import phases
from datasifter.graph.context import ExtractionCancelledError, build_extraction_context
from datasifter.graph.progress import AttributeState, ProgressTracker
from datasifter.graph.status import StatusEmitter
from datasifter.interfaces import (
    AttributeStore,
    JobRepository,
    MapEngine,
    ProgressSink,
    RetrievalProvider,
)
from datasifter.registry.registry import UnknownAttributeError, get_attribute_specs
from datasifter.schemas import (
    AttributeResult,
    AttributeSpec,
    ExtractionRequest,
    ExtractionResult,
    JobState,
    JobStatus,
    RetrievalConfig,
    StatusEvent,
)


@dataclass(slots=True)
class RunnerDefaults:
    model_name: str
    model_version: str
    retrieval: RetrievalConfig


@dataclass(slots=True)
class ExtractionOutcome:
    job: JobState
    result: ExtractionResult
    attributes: dict[str, AttributeResult]


AttributeSpecResolver = Callable[[str, Sequence[str] | None], Sequence[AttributeSpec]]
MapEngineFactory = Callable[[str], MapEngine]


class ExtractionRunner:
    def __init__(
        self,
        *,
        job_repository: JobRepository,
        attribute_store: AttributeStore,
        retrieval_provider: RetrievalProvider,
        map_engine_factory: MapEngineFactory,
        defaults: RunnerDefaults,
        progress_sink: ProgressSink | None = None,
        spec_resolver: AttributeSpecResolver = get_attribute_specs,
    ) -> None:
        self._job_repo = job_repository
        self._attribute_store = attribute_store
        self._retriever = retrieval_provider
        self._map_engine_factory = map_engine_factory
        self._defaults = defaults
        self._progress_sink = progress_sink
        self._spec_resolver = spec_resolver

    def _resolve_model(self, request: ExtractionRequest) -> str:
        return request.model or self._defaults.model_name

    def _resolve_retrieval(self, request: ExtractionRequest) -> RetrievalConfig:
        if request.retriever is not None:
            return request.retriever.model_copy(deep=True)
        return self._defaults.retrieval.model_copy(deep=True)

    async def run(
        self,
        request: ExtractionRequest,
        *,
        job: JobState | None = None,
    ) -> ExtractionOutcome:
        model_name = self._resolve_model(request)
        retrieval_config = self._resolve_retrieval(request)
        job_state = await self._job_repo.prepare_job(
            request=request,
            job=job,
            retrieval_config=retrieval_config,
            model_name=model_name,
            model_version=self._defaults.model_version,
        )

        if job_state.status == JobStatus.CANCELED:
            cancel_msg = job_state.error or "canceled by user"
            result = ExtractionResult.from_job(job_state, error_msg=cancel_msg)
            return ExtractionOutcome(job=job_state, result=result, attributes={})

        try:
            attribute_specs = list(
                self._spec_resolver(request.doc_type, request.attributes)
            )
        except UnknownAttributeError as exc:
            error_msg = f"Unknown attribute(s) in request: {exc}"
            result = ExtractionResult.from_job(job_state, error_msg=error_msg)
            return ExtractionOutcome(job=job_state, result=result, attributes={})

        progress = ProgressTracker(total_attributes=len(attribute_specs))
        states = {spec.name: AttributeState(spec.name) for spec in attribute_specs}
        emitter = StatusEmitter(
            job=job_state,
            job_repository=self._job_repo,
            progress=progress,
            attribute_states=states,
            sink=self._progress_sink,
        )
        context = build_extraction_context(
            request=request,
            job=job_state,
            retrieval_config=retrieval_config,
            retriever=self._retriever,
            map_engine=self._map_engine_factory(model_name),
            attribute_store=self._attribute_store,
            job_repository=self._job_repo,
            progress=progress,
            attribute_states=states,
            emitter=emitter,
        )

        await emitter.emit(StatusEvent.JOB_STARTED, include_snapshot=True)

        errors: list[str] = []
        results: dict[str, AttributeResult] = {}

        try:
            for spec in attribute_specs:
                attr_state = context.attribute_states[spec.name]
                attr_state.state = "mapping"
                await context.ensure_active()
                await context.emitter.emit(
                    StatusEvent.ATTRIBUTE_STARTED,
                    attribute_payload={"name": spec.name, "phase": "retrieve"},
                    include_snapshot=True,
                )
                map_chunks = await phases.retrieve_attribute_chunks(
                    context, spec, attr_state
                )
                candidates = await phases.map_attribute_chunks(
                    context, spec, map_chunks, attr_state
                )
                aggregate = await phases.reduce_attribute(
                    context, spec, candidates, attr_state
                )
                validated = await phases.validate_attribute(
                    context, spec, aggregate, len(map_chunks), attr_state
                )
                results[spec.name] = await phases.threshold_and_persist(
                    context,
                    spec,
                    validated,
                    candidates,
                    len(map_chunks),
                    attr_state,
                )

            job_state = await self._job_repo.update_status(
                job_state, status=JobStatus.COMPLETED
            )
            await emitter.emit(
                StatusEvent.JOB_COMPLETED,
                status_override=JobStatus.COMPLETED,
                include_snapshot=True,
                results={
                    name: {
                        "value": result.value,
                        "confidence": result.confidence,
                        "provenance": list(result.provenance),
                    }
                    for name, result in results.items()
                },
            )
        except ExtractionCancelledError:
            cancel_msg = "canceled by user"
            errors.append(cancel_msg)
            job_state = await self._job_repo.update_status(
                job_state, status=JobStatus.CANCELED, error=cancel_msg
            )
            await emitter.emit(
                StatusEvent.JOB_CANCELED,
                status_override=JobStatus.CANCELED,
                errors=errors,
                include_snapshot=True,
            )
        except Exception as exc:  # noqa: BLE001
            error_msg = str(exc)
            errors.append(error_msg)
            job_state = await self._job_repo.update_status(
                job_state, status=JobStatus.FAILED, error=error_msg
            )
            await emitter.emit(
                StatusEvent.JOB_FAILED,
                status_override=JobStatus.FAILED,
                errors=errors,
                include_snapshot=True,
            )
            raise

        result = ExtractionResult.from_job(
            job_state, attributes=results, error_msg=errors
        )
        return ExtractionOutcome(job=job_state, result=result, attributes=results)


__all__ = ["ExtractionRunner", "ExtractionOutcome", "RunnerDefaults"]

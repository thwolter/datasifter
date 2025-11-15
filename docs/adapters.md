# Adapters & Contracts

DataSifter intentionally avoids hard dependencies on storage engines, LLM providers, or messaging systems. Instead, it relies on a small set of `Protocol` interfaces located in `datasifter.interfaces`. Implement these adapters once per backend and reuse them anywhere you instantiate the runner.

## Overview

| Protocol | Responsibility | Typical backend implementation |
| --- | --- | --- |
| `JobRepository` | Persist job lifecycle (`prepare_job`, `update_status`, `refresh`, sequence numbers). | SQL table, Mongo collection, Redis hash. |
| `AttributeStore` | Store the final `AttributeResult` for each spec. | JSON column, document DB, observability index. |
| `RetrievalProvider` | Retrieve contextual `RetrievedChunk` objects before the map phase. | Vector DB query, OCR page fetcher, deterministic splitter. |
| `MapEngine` | Run the LLM or heuristic mapper to produce `Candidate`s. | OpenAI/Azure clients, local vLLM, rule-based parser. |
| `ProgressSink` | Publish `ExtractionStatusPayload` to downstream consumers. | Kafka topic, WebSocket broadcaster, logging sink. |

All protocols are asynchronous and should avoid blocking the event loop.

## JobRepository

```python
class JobRepository(Protocol):
    async def prepare_job(...) -> JobState: ...
    async def update_status(...) -> JobState: ...
    async def refresh(self, job: JobState) -> JobState: ...
    async def increment_sequence(self, job: JobState) -> int: ...
```

Implementation tips:

- `prepare_job` should be idempotent; create a new row if `job` is `None`, or update timestamps if it already exists.
- `increment_sequence` backs the optimistic concurrency built into some adapters (e.g., deduplicating status events). Persist and return the new integer atomically.
- Persist error messages and timestamps inside `JobState` so `ExtractionOutcome` stays informative.

## AttributeStore

```python
class AttributeStore(Protocol):
    async def persist(
        self, job: JobState, spec: AttributeSpec, result: AttributeResult
    ) -> None: ...
```

- Persist both the raw value and the provenance (list of chunk identifiers) for auditability.
- Consider storing a hash of `result.value` to simplify deduplication between runs.
- Implementations should be idempotent; the runner might replay `persist` during retries if no acknowledgement was recorded.

## RetrievalProvider

```python
class RetrievalProvider(Protocol):
    async def retrieve(
        *,
        job: JobState,
        request: ExtractionRequest,
        attribute: AttributeSpec,
        config: RetrievalConfig,
    ) -> Sequence[RetrievedChunk]: ...
```

- Interpret `RetrievalConfig` however you want: vector similarity threshold, reranking flag, `top_k`, etc.
- Each `RetrievedChunk` should contain the text, metadata, and an identifier (page, paragraph, table cell). This identifier later appears in provenance.
- If you need to run multiple retrieval strategies (e.g., dense + sparse), aggregate the results before returning them; the runner will respect ordering and `top_m`.

## MapEngine

```python
class MapEngine(Protocol):
    async def extract_candidate(
        *,
        doc_type: str,
        attribute: AttributeSpec,
        chunk: RetrievedChunk,
        attempt: int,
        prompt_id: str | None = None,
    ) -> Candidate: ...
```

- The runner injects `attempt` numbers so you can apply temperature annealing, fallback prompts, or context-window adaptations.
- Pull prompt templates from `attribute.prompts` or `datasifter.prompts` to keep instructions versioned with code.
- Return structured rationales to explain why the candidate value was selected; they become part of the reduction trace.

## ProgressSink

```python
class ProgressSink(Protocol):
    async def publish(self, payload: ExtractionStatusPayload) -> None: ...
```

- `payload.event` matches the `StatusEvent` enum (job started, attribute validated, etc.).
- Persist `payload.snapshot` if you need point-in-time telemetry with counts of mapped chunks, validated attributes, and so on.
- Multiple consumers can subscribe if you broadcast via a message broker or WebSocket hub.

## Putting adapters together

```python
runner = ExtractionRunner(
    job_repository=SqlJobRepository(db),
    attribute_store=JsonAttributeStore(db),
    retrieval_provider=HybridRetriever(vector_db, blob_storage),
    map_engine_factory=lambda model: OpenAIMapEngine(model=model, api_key=env.API_KEY),
    progress_sink=KafkaProgressSink(topic="datasifter.status"),
    defaults=RunnerDefaults(...),
)
```

Ensure every adapter is thoroughly unit-tested; place fixtures under `tests/fixtures/` to mock LLMs or databases as recommended in the repository guidelines.

## Postgres / SQLModel defaults

DataSifter now ships optional helpers for SQLModel-backed Postgres deployments inside `datasifter.adapters.postgres`. They encapsulate the orchestration logic while letting you plug in your own SQLModel models and persistence helpers:

```python
from datasifter.adapters.postgres import SqlModelJobRepository, SqlModelAttributeStore
from extraction.models import ExtractionJob, ExtractionJobStatus
from extraction.persistence import (
    create_extraction_job,
    increment_sequence,
    persist_attribute,
    update_job_status,
)

job_repo = SqlModelJobRepository(
    session=session,
    job_model=ExtractionJob,
    status_factory=lambda status: ExtractionJobStatus(status.value),
    create_job=create_extraction_job,
    update_job_status=update_job_status,
    increment_sequence=increment_sequence,
)

attribute_store = SqlModelAttributeStore(
    session=session,
    job_model=ExtractionJob,
    persist_attribute=persist_attribute,
)
```

The helpers expect:

- A SQLModel `AsyncSession` instance (`session`).
- Your SQLModel job model (`job_model`) and status enum conversion (`status_factory`).
- Coroutine callables that create jobs, update statuses, increment sequences, and persist individual attributes.

Because the SQLModel helpers store the ORM instance on `JobState.context["orm"]`, attribute persistence and job refreshes remain efficient even across retries.

## Adapter stubs

To kickstart custom implementations without copying docstrings around, import the ready-made skeletons from `datasifter.adapters.stubs`:

```python
from datasifter.adapters.stubs import StubJobRepository, StubRetrievalProvider

class FirestoreJobRepository(StubJobRepository):
    async def prepare_job(...):
        ...
```

Every stub raises `NotImplementedError` so your code fails fast until the implementation is filled in. Use them as scaffolding in sample projects or tutorials.

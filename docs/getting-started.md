# Installation & Requirements

This guide walks through the prerequisites, installation paths, and the minimal amount of code needed to wire DataSifter into your own backend.

## Runtime requirements

- **Python**: `>=3.12` (matches `pyproject.toml`).
- **Package manager**: `uv` is recommended for rapid locking (`uv pip sync`) but the package also works with `pip`.
- **LLM access**: bring any provider that can implement the `MapEngine` protocol (OpenAI, Azure, local models, etc.).
- **Storage**: implement `JobRepository` and `AttributeStore` using your persistence layer (SQL, document store, message bus, …).
- **Retrieval stack**: anything that can return ranked chunks (`RetrievalProvider`). This could be a vector DB, RAG API, or deterministic splitter.

## Installing the package

### Using uv (recommended for local development)

```bash
uv pip install datasifter
# or keep the repo in editable mode
uv pip install -e .
```

After changing dependencies, run:

```bash
uv pip sync
```

### Using pip

```bash
python -m venv .venv
source .venv/bin/activate
pip install datasifter
```

When contributing to this repository, make sure to install the development dependencies:

```bash
uv pip install -e ".[dev]"
```

## Local tooling commands

- `uv run pytest` – run the entire test suite.
- `uv run ruff check src tests` – linting.
- `uv run ruff format src tests` – formatting.
- `uv run mkdocs serve` – preview this documentation at `http://127.0.0.1:8000`.

## Configuring runner defaults

Every `ExtractionRunner` needs defaults for model and retrieval behavior. A typical configuration lives next to your service wiring:

```python
from datasifter.runner import ExtractionRunner, RunnerDefaults
from datasifter.schemas import RetrievalConfig

runner = ExtractionRunner(
    job_repository=MyJobRepository(),
    attribute_store=MyAttributeStore(),
    retrieval_provider=MyRetriever(),
    map_engine_factory=lambda model_name: MyLLMMapEngine(model=model_name),
    progress_sink=MyProgressSink(),
    defaults=RunnerDefaults(
        model_name="gpt-4o-mini",
        model_version="2024-08-06",
        retrieval=RetrievalConfig(
            top_k=12,
            top_m=6,
            similarity_threshold=0.68,
            rerank=True,
        ),
    ),
)
```

You can override any of these defaults per request by supplying `ExtractionRequest.model` or `ExtractionRequest.retriever`.

## Minimal extraction example

```python
from datasifter.runner import ExtractionRunner, RunnerDefaults
from datasifter.schemas import ExtractionRequest, RetrievalConfig

async def extract_invoice(invoice_id: str) -> None:
    request = ExtractionRequest(
        job_id=invoice_id,
        doc_type="invoice",
        document_uri=f"s3://raw-invoices/{invoice_id}.pdf",
        attributes=["invoice_number", "total", "due_date"],
    )

    outcome = await runner.run(request)
    if outcome.result.status.is_failure:
        # react accordingly
        raise RuntimeError(outcome.result.error)
```

Wrap this call inside your job processor, API handler, or message consumer. The runner will:

1. Ask your `JobRepository` to create/resume the job and status timeline.
2. Resolve attribute specs from the registry (`datasifter.registry`).
3. Retrieve contextual chunks, call your `MapEngine`, validate, threshold, and persist attributes.
4. Emit structured progress objects to `ProgressSink` so clients can subscribe.

Move on to the [Workflow Deep Dive](workflow.md) once the environment is ready—you will see how each phase behaves and which events are emitted.

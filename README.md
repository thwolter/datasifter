# datasifter

Core extraction orchestration primitives that can be reused across backends. Datasifter exposes:

- Pydantic schemas and registries for describing document attributes.
- Protocol-driven orchestration runner that wires retrieval, mapping, and persistence via adapters.
- Validation, reduction, and threshold helpers for attribute-centric pipelines.

The package intentionally ships without IO dependencies (database, message bus, FastAPI). Bring your own adapters that satisfy the provided protocols.
Optional SQLModel/Postgres defaults live under `datasifter.adapters.postgres` so job repositories and attribute stores can be wired without rewriting boilerplate.

## Configuration

- `datasifter.settings.Settings` mirrors the configuration layout used in `../metis/src/core/config.py` and exposes nested `AdapterSettings`/`ExtractionSettings` Pydantic models.
- Call `Settings.from_env()` or `datasifter.get_settings()` to load values from `DATASIFTER_*` environment variables (`DATASIFTER_ADAPTERS__RETRIEVAL_PROVIDER=pgvector`, `DATASIFTER_EXTRACTION__RETRIEVAL__TOP_M=6`, etc.).
- Adapter fields hold string identifiers or import paths so deployments can toggle between Postgres/MySQL repositories, vector stores, or LLM providers without touching application code.

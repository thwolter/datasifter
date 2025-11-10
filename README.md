# datasifter

Core extraction orchestration primitives that can be reused across backends. Datasifter exposes:

- Pydantic schemas and registries for describing document attributes.
- Protocol-driven orchestration runner that wires retrieval, mapping, and persistence via adapters.
- Validation, reduction, and threshold helpers for attribute-centric pipelines.

The package intentionally ships without IO dependencies (database, message bus, FastAPI). Bring your own adapters that satisfy the provided protocols.

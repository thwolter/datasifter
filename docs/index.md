# DataSifter

DataSifter extracts document attributes using a pluggable runner. It contains the domain models, orchestration phases, and helper utilities while leaving infrastructure (web APIs, databases, queues) to the host backend.

## Why another package?

Metis originally embedded the entire pipeline together with its persistence layer, which made reuse in other stacks painful. DataSifter moves the pure orchestration logic into a standalone library so any backend can supply its own persistence and messaging adapters.

## High-level workflow

1. Build adapters that satisfy the provided `JobRepository`, `AttributeStore`, `RetrievalProvider`, `MapEngine`, and `ProgressSink` protocols.
2. Instantiate an `ExtractionRunner` with your adapters and optional defaults (model name, retrieval config).
3. Call `await runner.run(request)` inside your task or request handler and stream the emitted status events to your transport of choice.

See `docs/adapters.md` for detailed diagrams and extension points.

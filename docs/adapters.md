# Adapter Interfaces

The runner orchestrates attribute extraction by collaborating with the following protocols:

- **JobRepository** – create or resume extraction jobs and persist status transitions.
- **AttributeStore** – persist final attribute payloads for a job.
- **RetrievalProvider** – return ranked `RetrievedChunk` instances for a given attribute.
- **MapEngine** – perform the LLM map step and produce `Candidate` objects.
- **ProgressSink** – publish `StatusEvent` payloads to any transport (websocket, broker, logs).

Each protocol lives in `datasifter.interfaces`. Reference implementations live in Metis, but any backend can write its own adapters that hit different databases or LLM providers.

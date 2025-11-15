from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Mapping, MutableMapping

from pydantic import BaseModel, Field

from .schemas import RetrievalConfig

ENV_PREFIX = "DATASIFTER_"
NESTED_DELIMITER = "__"


class AdapterSettings(BaseModel):
    """String targets describing which adapters to load for each interface."""

    job_repository: str = Field(
        default="memory",
        description="Identifier or import path for the JobRepository adapter.",
    )
    attribute_store: str = Field(
        default="memory",
        description="Identifier or import path for AttributeStore persistence.",
    )
    retrieval_provider: str = Field(
        default="memory",
        description="Identifier or import path for the RetrievalProvider.",
    )
    map_engine: str = Field(
        default="memory",
        description="Identifier or import path for the MapEngine factory.",
    )
    progress_sink: str | None = Field(
        default=None,
        description="Optional identifier or import path for a ProgressSink.",
    )


class ExtractionSettings(BaseModel):
    """Execution settings that mirror Metis' defaults without the IO bindings."""

    default_model: str = Field(
        default="openai:gpt-4o-mini", description="LLM used when the request omits one."
    )
    model_version: str = Field(
        default="2024-06-01", description="Version tag persisted alongside results."
    )
    retrieval: RetrievalConfig = Field(
        default_factory=RetrievalConfig,
        description="Baseline RetrievalConfig applied to incoming requests.",
    )


class Settings(BaseModel):
    """Pydantic powered settings structure with env overrides for deployments."""

    env: str = Field(default="production", description="Deployment environment label.")
    adapters: AdapterSettings = Field(default_factory=AdapterSettings)
    extraction: ExtractionSettings = Field(default_factory=ExtractionSettings)

    @classmethod
    def from_env(
        cls, env: Mapping[str, str] | None = None, **overrides: Any
    ) -> "Settings":
        """Load settings from DATASIFTER_* environment variables."""

        env_data = _build_env_payload(env or os.environ)
        if overrides:
            env_data.update(overrides)
        return cls.model_validate(env_data)


def _build_env_payload(env: Mapping[str, str]) -> MutableMapping[str, Any]:
    """Convert DATASIFTER_* environment variables into a nested payload."""

    payload: MutableMapping[str, Any] = {}
    for raw_key, value in env.items():
        if not raw_key.startswith(ENV_PREFIX):
            continue
        trimmed = raw_key[len(ENV_PREFIX) :]
        if not trimmed:
            continue
        parts = [segment.strip().lower() for segment in trimmed.split(NESTED_DELIMITER)]
        current: MutableMapping[str, Any] = payload
        for segment in parts[:-1]:
            if not segment:
                continue
            current = current.setdefault(segment, {})
        if parts:
            current[parts[-1]] = value
    return payload


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance that mirrors metis/core/config defaults."""

    return Settings.from_env()


__all__ = ["AdapterSettings", "ExtractionSettings", "Settings", "get_settings"]

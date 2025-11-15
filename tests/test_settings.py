from __future__ import annotations

import pytest

from datasifter.settings import Settings, get_settings


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    try:
        yield
    finally:
        get_settings.cache_clear()


def test_settings_from_env_parses_nested_values():
    env = {
        "DATASIFTER_ENV": "development",
        "DATASIFTER_ADAPTERS__JOB_REPOSITORY": "postgres",
        "DATASIFTER_EXTRACTION__RETRIEVAL__TOP_M": "7",
    }
    settings = Settings.from_env(env)

    assert settings.env == "development"
    assert settings.adapters.job_repository == "postgres"
    assert settings.extraction.retrieval.top_m == 7


def test_get_settings_uses_process_environment(monkeypatch):
    monkeypatch.setenv("DATASIFTER_ENV", "staging")
    monkeypatch.setenv("DATASIFTER_ADAPTERS__MAP_ENGINE", "openai:gpt-4o-mini")
    settings = get_settings()

    assert settings.env == "staging"
    assert settings.adapters.map_engine == "openai:gpt-4o-mini"


def test_get_settings_is_cached(monkeypatch):
    monkeypatch.setenv("DATASIFTER_ENV", "dev")
    first = get_settings()
    monkeypatch.setenv("DATASIFTER_ENV", "prod")

    second = get_settings()
    assert first is second
    assert second.env == "dev"

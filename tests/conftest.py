from __future__ import annotations

import pytest

from datasifter.runner import RunnerDefaults
from datasifter.schemas import AttributeType, RetrievalConfig, Thresholds
from datasifter.registry import registry as registry_module

from .fixtures.factories import make_attribute_spec, make_job_state, make_request
from .fixtures.fakes import (
    FakeAttributeStore,
    FakeJobRepository,
    FakeMapEngine,
    FakeProgressSink,
    FakeRetrievalProvider,
)


@pytest.fixture
def runner_defaults() -> RunnerDefaults:
    return RunnerDefaults(
        model_name="default-model",
        model_version="1.0",
        retrieval=RetrievalConfig(),
    )


@pytest.fixture
def sample_spec():
    return make_attribute_spec(
        name="total_due",
        attr_type=AttributeType.STRING,
        thresholds=Thresholds(min_confidence=0.5, min_chunks=1),
    )


@pytest.fixture
def job_state():
    return make_job_state()


@pytest.fixture
def extraction_request():
    return make_request()


@pytest.fixture
def attribute_store():
    return FakeAttributeStore()


@pytest.fixture
def progress_sink():
    return FakeProgressSink()


@pytest.fixture
def retriever():
    return FakeRetrievalProvider([])


@pytest.fixture
def map_engine():
    return FakeMapEngine()


@pytest.fixture
def job_repository(job_state):
    return FakeJobRepository(job_state)


@pytest.fixture(autouse=True)
def reset_registry():
    snapshot = {
        doc: specs.copy() for doc, specs in registry_module.get_registry().items()
    }
    registry_module._REGISTRY.clear()
    try:
        yield
    finally:
        registry_module._REGISTRY.clear()
        for doc, specs in snapshot.items():
            registry_module._REGISTRY[doc] = dict(specs)

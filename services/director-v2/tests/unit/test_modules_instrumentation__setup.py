# pylint: disable=redefined-outer-name

import pytest
from fastapi import FastAPI
from prometheus_client import CollectorRegistry
from simcore_service_director_v2.core.errors import ConfigurationError
from simcore_service_director_v2.modules.instrumentation import (
    get_instrumentation,
    has_instrumentation,
)
from simcore_service_director_v2.modules.instrumentation._models import (
    DirectorV2Instrumentation,
)


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
def instrumentation() -> DirectorV2Instrumentation:
    return DirectorV2Instrumentation(registry=CollectorRegistry())


def test_has_instrumentation_is_false_when_not_configured(app: FastAPI):
    assert has_instrumentation(app) is False


def test_get_instrumentation_raises_configuration_error_when_not_configured(app: FastAPI):
    with pytest.raises(ConfigurationError):
        get_instrumentation(app)


def test_get_instrumentation_when_configured(app: FastAPI, instrumentation: DirectorV2Instrumentation):
    app.state.instrumentation = instrumentation

    assert has_instrumentation(app) is True
    assert get_instrumentation(app) is instrumentation

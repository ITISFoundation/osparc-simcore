# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument


import urllib.parse
from collections.abc import Iterator

import pytest
import respx
from fastapi import FastAPI
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_dynamic_scheduler.services.catalog import CatalogPublicClient


@pytest.fixture
def app_environment(
    disable_redis_setup: None,
    disable_rabbitmq_setup: None,
    disable_service_tracker_setup: None,
    disable_deferred_manager_setup: None,
    disable_notifier_setup: None,
    disable_status_monitor_setup: None,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment


@pytest.fixture
def simcore_service_labels() -> SimcoreServiceLabels:
    return TypeAdapter(SimcoreServiceLabels).validate_python(
        SimcoreServiceLabels.model_json_schema()["examples"][1]
    )


@pytest.fixture
def service_specifications() -> ServiceSpecifications:
    return TypeAdapter(ServiceSpecifications).validate_python({})


@pytest.fixture
def user_id() -> UserID:
    return 1


@pytest.fixture
def service_version() -> ServiceVersion:
    return "1.0.0"


@pytest.fixture
def service_key() -> ServiceKey:
    return "simcore/services/dynamic/test"


@pytest.fixture
def mock_catalog(
    app: FastAPI,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    simcore_service_labels: SimcoreServiceLabels,
    service_specifications: ServiceSpecifications,
) -> Iterator[None]:
    with respx.mock(
        base_url=app.state.settings.DYNAMIC_SCHEDULER_CATALOG_SETTINGS.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as respx_mock:
        respx_mock.get(
            f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}/labels",
            name="service labels",
        ).respond(
            status_code=200,
            json=simcore_service_labels.model_dump(mode="json"),
        )

        respx_mock.get(
            f"/services/{urllib.parse.quote_plus(service_key)}/{service_version}/specifications?user_id={user_id}",
            name="service specifications",
        ).respond(
            status_code=200,
            json=service_specifications.model_dump(mode="json"),
        )

        yield


async def test_get_services_labels(
    mock_catalog: None,
    app: FastAPI,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    simcore_service_labels: SimcoreServiceLabels,
):
    client = CatalogPublicClient.get_from_app_state(app)
    result = await client.get_services_labels(service_key, service_version)
    assert result.model_dump(mode="json") == simcore_service_labels.model_dump(
        mode="json"
    )


async def test_get_services_specifications(
    mock_catalog: None,
    app: FastAPI,
    user_id: UserID,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    service_specifications: ServiceSpecifications,
):
    client = CatalogPublicClient.get_from_app_state(app)
    result = await client.get_services_specifications(
        user_id, service_key, service_version
    )
    assert result.model_dump(mode="json") == service_specifications.model_dump(
        mode="json"
    )

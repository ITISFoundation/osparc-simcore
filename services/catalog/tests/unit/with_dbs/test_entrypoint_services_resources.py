# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import urllib.parse
from random import choice, randint
from typing import Any, Callable

import httpx
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.services_resources import ResourceValue, ServiceResources
from pydantic import ByteSize
from respx.models import Route
from simcore_service_catalog.core.settings import _DEFAULT_SERVICE_RESOURCES
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def service_labels(faker: Faker) -> Callable[..., dict[str, Any]]:
    def creator():
        return {faker.get_label(): faker.text()}

    return creator


@pytest.fixture
def service_key(faker: Faker) -> str:
    return f"simcore/services/{choice(['comp', 'dynamic','frontend'])}/jupyter-math"


@pytest.fixture
def service_version() -> str:
    return f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"


@pytest.fixture
def mock_service_labels(faker: Faker) -> dict[str, Any]:
    return {
        "simcore.service.settings": '[ {"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}, {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 } } } ]',
    }


@pytest.fixture
def mock_director_service_labels(
    director_mockup: respx.MockRouter, app: FastAPI
) -> Route:
    slash = urllib.parse.quote_plus("/")
    mock_route = director_mockup.get(
        url__regex=rf"v0/services/simcore{slash}services{slash}(comp|dynamic|frontend)({slash}[\w{slash}-]+)+/[0-9]+.[0-9]+.[0-9]+/labels",
        name="get_service_labels",
    ).respond(200, json={"data": {}})

    return mock_route


@pytest.mark.parametrize(
    "director_labels, expected_resources",
    [
        pytest.param(
            {},
            _DEFAULT_SERVICE_RESOURCES,
            id="nothing_defined_returns_default_resources",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 } } } ]',
            },
            _DEFAULT_SERVICE_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(
                            limit=4.0,
                            reservation=_DEFAULT_SERVICE_RESOURCES["CPU"].reservation,
                        ),
                        "RAM": ResourceValue(
                            limit=ByteSize(17179869184),
                            reservation=_DEFAULT_SERVICE_RESOURCES["RAM"].reservation,
                        ),
                    },
                }
            ),
            id="only_limits_defined_returns_default_reservations",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "constraints", "type": "string", "value": [ "node.platform.os == linux" ]}, {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 }, "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } }, { "NamedResourceSpec": { "Kind": "SOME_STUFF", "Value": "some_string" } } ] } } } ]'
            },
            _DEFAULT_SERVICE_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(limit=4.0, reservation=0.1),
                        "RAM": ResourceValue(
                            limit=ByteSize(17179869184), reservation=ByteSize(536870912)
                        ),
                        "VRAM": ResourceValue(limit=0, reservation=1),
                        "SOME_STUFF": ResourceValue(limit=0, reservation="some_string"),
                    }
                }
            ),
            id="everything_rightly_defined",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [  ] } } } ]'
            },
            _DEFAULT_SERVICE_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(
                            limit=_DEFAULT_SERVICE_RESOURCES["CPU"].limit,
                            reservation=0.1,
                        ),
                        "RAM": ResourceValue(
                            limit=_DEFAULT_SERVICE_RESOURCES["RAM"].limit,
                            reservation=ByteSize(536870912),
                        ),
                    }
                }
            ),
            id="no_limits_defined_returns_default_limits",
        ),
        pytest.param(
            {
                "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 10000000000, "MemoryBytes": 53687091232, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } } ] } } } ]'
            },
            _DEFAULT_SERVICE_RESOURCES.copy(
                update={
                    "__root__": {
                        "CPU": ResourceValue(
                            limit=10.0,
                            reservation=10.0,
                        ),
                        "RAM": ResourceValue(
                            limit=ByteSize(53687091232),
                            reservation=ByteSize(53687091232),
                        ),
                        "VRAM": ResourceValue(limit=0, reservation=1),
                    }
                }
            ),
            id="no_limits_with_reservations_above_default_returns_same_as_reservation",
        ),
    ],
)
async def test_get_service_resources(
    mock_catalog_background_task,
    mock_director_service_labels: Route,
    client: TestClient,
    director_labels: dict[str, Any],
    expected_resources: ServiceResources,
):
    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    mock_director_service_labels.respond(json={"data": director_labels})
    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    response = client.get(f"{url}")
    assert response.status_code == 200, f"{response.text}"
    data = response.json()
    received_resources = ServiceResources.parse_obj(data)
    assert received_resources == expected_resources


async def test_get_service_resources_raises_errors(
    mock_catalog_background_task,
    mock_director_service_labels: Route,
    client: TestClient,
):
    service_key = f"simcore/services/{choice(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{randint(0,100)}.{randint(0,100)}.{randint(0,100)}"
    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    # simulate a communication error
    mock_director_service_labels.side_effect = httpx.HTTPError
    response = client.get(f"{url}")
    assert response.status_code == httpx.codes.SERVICE_UNAVAILABLE, f"{response.text}"
    # simulate a missing service
    mock_director_service_labels.respond(
        httpx.codes.NOT_FOUND, json={"error": "service not found"}
    )
    response = client.get(f"{url}")
    assert response.status_code == httpx.codes.NOT_FOUND, f"{response.text}"

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import urllib.parse
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
import respx
from faker import Faker
from fastapi.encoders import jsonable_encoder
from models_library.docker import DockerGenericTag
from models_library.services_resources import (
    BootMode,
    ResourcesDict,
    ResourceValue,
    ServiceResourcesDict,
    ServiceResourcesDictHelpers,
)
from pydantic import ByteSize, TypeAdapter
from respx.models import Route
from simcore_service_catalog.core.settings import _DEFAULT_RESOURCES
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def mocked_director_service_labels(
    mocked_director_service_api_base: respx.MockRouter,
) -> Route:
    """
    Customizes mock for labels entrypoints at the director service's API
    """
    slash = urllib.parse.quote_plus("/")
    return mocked_director_service_api_base.get(
        url__regex=rf"v0/services/simcore{slash}services{slash}(comp|dynamic|frontend)({slash}[\w{slash}-]+)+/[0-9]+.[0-9]+.[0-9]+/labels",
        name="get_service_labels",
    ).respond(200, json={"data": {}})


@pytest.fixture
def service_labels(faker: Faker) -> Callable[..., dict[str, Any]]:
    def creator():
        return {faker.get_label(): faker.text()}

    return creator


@pytest.fixture
def service_key(faker: Faker) -> str:
    return f"simcore/services/{faker.random_element(['comp', 'dynamic','frontend'])}/jupyter-math"


@pytest.fixture
def service_version(faker: Faker) -> str:
    return (
        f"{faker.random_int(0,100)}.{faker.random_int(0,100)}.{faker.random_int(0,100)}"
    )


@pytest.fixture
def mock_service_labels() -> dict[str, Any]:
    return {
        "simcore.service.settings": '[ {"name": "ports", "type": "int", "value": 8888}, {"name": "constraints", "type": "string", "value": ["node.platform.os == linux"]}, {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 } } } ]',
    }


def _update_copy(dict_data: dict, update: dict) -> dict:
    dict_data_copy = deepcopy(dict_data)
    dict_data_copy.update(update)
    return dict_data_copy


@dataclass
class _ServiceResourceParams:
    simcore_service_label: dict[str, str]
    expected_resources: ResourcesDict
    expected_boot_modes: list[BootMode]


@pytest.mark.parametrize(
    "params",
    [
        pytest.param(
            _ServiceResourceParams({}, _DEFAULT_RESOURCES, [BootMode.CPU]),
            id="nothing_defined_returns_default_resources",
        ),
        pytest.param(
            _ServiceResourceParams(
                {
                    "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 } } } ]',
                },
                _update_copy(
                    _DEFAULT_RESOURCES,
                    {
                        "CPU": ResourceValue(
                            limit=4.0,
                            reservation=_DEFAULT_RESOURCES["CPU"].reservation,
                        ),
                        "RAM": ResourceValue(
                            limit=ByteSize(17179869184),
                            reservation=_DEFAULT_RESOURCES["RAM"].reservation,
                        ),
                    },
                ),
                [BootMode.CPU],
            ),
            id="only_limits_defined_returns_default_reservations",
        ),
        pytest.param(
            _ServiceResourceParams(
                {
                    "simcore.service.settings": '[ {"name": "constraints", "type": "string", "value": [ "node.platform.os == linux" ]}, {"name": "Resources", "type": "Resources", "value": { "Limits": { "NanoCPUs": 4000000000, "MemoryBytes": 17179869184 }, "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } }, { "NamedResourceSpec": { "Kind": "AIRAM", "Value": "some_string" } } ] } } } ]'
                },
                _update_copy(
                    _DEFAULT_RESOURCES,
                    {
                        "CPU": ResourceValue(limit=4.0, reservation=0.1),
                        "RAM": ResourceValue(
                            limit=ByteSize(17179869184), reservation=ByteSize(536870912)
                        ),
                        "VRAM": ResourceValue(limit=1, reservation=1),
                        "AIRAM": ResourceValue(limit=0, reservation="some_string"),
                    },
                ),
                [BootMode.GPU],
            ),
            id="everything_rightly_defined",
        ),
        pytest.param(
            _ServiceResourceParams(
                {
                    "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 100000000, "MemoryBytes": 536870912, "GenericResources": [  ] } } } ]'
                },
                _update_copy(
                    _DEFAULT_RESOURCES,
                    {
                        "CPU": ResourceValue(
                            limit=_DEFAULT_RESOURCES["CPU"].limit,
                            reservation=0.1,
                        ),
                        "RAM": ResourceValue(
                            limit=_DEFAULT_RESOURCES["RAM"].limit,
                            reservation=ByteSize(536870912),
                        ),
                    },
                ),
                [BootMode.CPU],
            ),
            id="no_limits_defined_returns_default_limits",
        ),
        pytest.param(
            _ServiceResourceParams(
                {
                    "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 10000000000, "MemoryBytes": 53687091232, "GenericResources": [ { "DiscreteResourceSpec": { "Kind": "VRAM", "Value": 1 } } ] } } } ]'
                },
                _update_copy(
                    _DEFAULT_RESOURCES,
                    {
                        "CPU": ResourceValue(
                            limit=10.0,
                            reservation=10.0,
                        ),
                        "RAM": ResourceValue(
                            limit=ByteSize(53687091232),
                            reservation=ByteSize(53687091232),
                        ),
                        "VRAM": ResourceValue(limit=1, reservation=1),
                    },
                ),
                [BootMode.GPU],
            ),
            id="no_limits_with_reservations_above_default_returns_same_as_reservation",
        ),
    ],
)
async def test_get_service_resources(
    background_tasks_setup_disabled,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_labels: Route,
    client: TestClient,
    params: _ServiceResourceParams,
    service_key: str,
    service_version: str,
) -> None:

    mocked_director_service_labels.respond(json={"data": params.simcore_service_label})
    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    response = client.get(f"{url}")
    assert response.status_code == 200, f"{response.text}"
    data = response.json()
    received_resources: ServiceResourcesDict = ServiceResourcesDict(**data)
    assert isinstance(received_resources, dict)

    expected_service_resources = ServiceResourcesDictHelpers.create_from_single_service(
        TypeAdapter(DockerGenericTag).validate_python(
            f"{service_key}:{service_version}"
        ),
        params.expected_resources,
        boot_modes=params.expected_boot_modes,
    )
    assert isinstance(expected_service_resources, dict)
    assert received_resources == jsonable_encoder(expected_service_resources)


@pytest.fixture
def create_mock_director_service_labels(
    mocked_director_service_api_base: respx.MockRouter,
) -> Callable:
    def factory(services_labels: dict[str, dict[str, Any]]) -> None:
        for service_name, data in services_labels.items():
            encoded_key = urllib.parse.quote_plus(
                f"simcore/services/dynamic/{service_name}"
            )
            for k, mock_key in enumerate((encoded_key, service_name)):
                mocked_director_service_api_base.get(
                    url__regex=rf"v0/services/{mock_key}/[\w/.]+/labels",
                    name=f"get_service_labels_for_{service_name}_{k}",
                ).respond(200, json={"data": data})

    return factory


@pytest.mark.parametrize(
    "mapped_services_labels, expected_service_resources, service_key, service_version",
    [
        pytest.param(
            {
                "sim4life-dy": {
                    "simcore.service.settings": '[ {"name": "Resources", "type": "Resources", "value": { "Reservations": { "NanoCPUs": 300000000, "MemoryBytes": 53687091232 } } } ]',
                    "simcore.service.compose-spec": '{"version": "2.3", "services": {"rt-web-dy":{"image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sim4life-dy:${SERVICE_VERSION}","init": true, "depends_on": ["s4l-core"]}, "s4l-core": {"image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/s4l-core-dy:${SERVICE_VERSION}","runtime": "nvidia", "init": true, "environment": ["DISPLAY=${DISPLAY}"],"volumes": ["/tmp/.X11-unix:/tmp/.X11-unix"]}, "sym-server": {"image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/sym-server:${SERVICE_VERSION}","init": true}}}',
                },
                "s4l-core-dy": {
                    "simcore.service.settings": '[{"name": "env", "type": "string", "value": ["DISPLAY=:0"]},{"name": "env", "type": "string", "value": ["SYM_SERVER_HOSTNAME=%%container_name.sym-server%%"]},{"name": "mount", "type": "object", "value": [{"ReadOnly": true, "Source":"/tmp/.X11-unix", "Target": "/tmp/.X11-unix", "Type": "bind"}]}, {"name":"constraints", "type": "string", "value": ["node.platform.os == linux"]},{"name": "Resources", "type": "Resources", "value": {"Limits": {"NanoCPUs":4000000000, "MemoryBytes": 17179869184}, "Reservations": {"NanoCPUs": 100000000,"MemoryBytes": 536870912, "GenericResources": [{"DiscreteResourceSpec":{"Kind": "VRAM", "Value": 1}}]}}}]'
                },
                "sym-server": {"simcore.service.settings": "[]"},
            },
            TypeAdapter(ServiceResourcesDict).validate_python(
                ServiceResourcesDictHelpers.model_config["json_schema_extra"][
                    "examples"
                ][1]
            ),
            "simcore/services/dynamic/sim4life-dy",
            "3.0.0",
            id="s4l_case",
        ),
        pytest.param(
            {
                "jupyter-math": {
                    "simcore.service.settings": "[]",
                    "simcore.service.compose-spec": '{"version": "2.3", "services": {"jupyter-math":{"image": "${SIMCORE_REGISTRY}/simcore/services/dynamic/jupyter-math:${SERVICE_VERSION}"}, "busybox": {"image": "busybox:1.2.3"}}}',
                },
                "busybox": {"simcore.service.settings": "[]"},
            },
            TypeAdapter(ServiceResourcesDict).validate_python(
                {
                    "jupyter-math": {
                        "image": "simcore/services/dynamic/jupyter-math:2.0.5",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": TypeAdapter(ByteSize).validate_python("2Gib"),
                                "reservation": TypeAdapter(ByteSize).validate_python(
                                    "2Gib"
                                ),
                            },
                        },
                    },
                    "busybox": {
                        "image": "busybox:1.2.3",
                        "resources": {
                            "CPU": {"limit": 0.1, "reservation": 0.1},
                            "RAM": {
                                "limit": TypeAdapter(ByteSize).validate_python("2Gib"),
                                "reservation": TypeAdapter(ByteSize).validate_python(
                                    "2Gib"
                                ),
                            },
                        },
                    },
                },
            ),
            "simcore/services/dynamic/jupyter-math",
            "2.0.5",
            id="using_an_external_image",
        ),
    ],
)
async def test_get_service_resources_sim4life_case(
    background_tasks_setup_disabled,
    rabbitmq_and_rpc_setup_disabled: None,
    create_mock_director_service_labels: Callable,
    client: TestClient,
    mapped_services_labels: dict[str, dict[str, Any]],
    expected_service_resources: ServiceResourcesDict,
    service_key: str,
    service_version: str,
) -> None:
    create_mock_director_service_labels(mapped_services_labels)

    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    response = client.get(f"{url}")
    assert response.status_code == 200, f"{response.text}"
    data = response.json()
    received_service_resources = TypeAdapter(ServiceResourcesDict).validate_python(data)

    assert received_service_resources == expected_service_resources


async def test_get_service_resources_raises_errors(
    background_tasks_setup_disabled,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_service_labels: Route,
    client: TestClient,
    service_key: str,
    service_version: str,
) -> None:

    url = URL(f"/v0/services/{service_key}/{service_version}/resources")
    # simulate a communication error
    mocked_director_service_labels.side_effect = httpx.HTTPError
    response = client.get(f"{url}")
    assert response.status_code == httpx.codes.SERVICE_UNAVAILABLE, f"{response.text}"
    # simulate a missing service
    mocked_director_service_labels.respond(
        httpx.codes.NOT_FOUND, json={"error": "service not found"}
    )
    response = client.get(f"{url}")
    assert response.status_code == httpx.codes.NOT_FOUND, f"{response.text}"

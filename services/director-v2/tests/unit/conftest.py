# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
import logging
import random
import urllib.parse
from collections.abc import AsyncIterable, Iterable, Iterator, Mapping
from typing import Any
from unittest import mock

import aiodocker
import pytest
import respx
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services import DynamicServiceCreate
from models_library.api_schemas_directorv2.dynamic_services_service import (
    ServiceDetails,
)
from models_library.basic_types import PortInt
from models_library.callbacks_mapping import CallbacksMapping
from models_library.clusters import ClusterID
from models_library.generated_models.docker_rest_api import (
    ServiceSpec as DockerServiceSpec,
)
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import RunID, ServiceKey, ServiceKeyVersion, ServiceVersion
from models_library.services_enums import ServiceState
from models_library.utils._original_fastapi_encoders import jsonable_encoder
from pydantic import TypeAdapter
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.s3 import S3Settings
from simcore_sdk.node_ports_v2 import FileLinkType
from simcore_service_director_v2.constants import DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.dynamic_services_scheduler import SchedulerData


@pytest.fixture
def disable_postgres(mocker) -> None:
    def mock_setup(app: FastAPI, *args, **kwargs) -> None:
        app.state.engine = mock.AsyncMock()

    mocker.patch("simcore_service_director_v2.modules.db.setup", side_effect=mock_setup)


@pytest.fixture
def simcore_services_network_name() -> str:
    return "test_network_name"


@pytest.fixture
def simcore_service_labels() -> SimcoreServiceLabels:
    simcore_service_labels = SimcoreServiceLabels.model_validate(
        SimcoreServiceLabels.model_config["json_schema_extra"]["examples"][1]
    )
    simcore_service_labels.callbacks_mapping = CallbacksMapping.model_validate({})
    return simcore_service_labels


@pytest.fixture
def dynamic_service_create() -> DynamicServiceCreate:
    return DynamicServiceCreate.model_validate(
        DynamicServiceCreate.model_config["json_schema_extra"]["example"]
    )


@pytest.fixture
def dynamic_sidecar_port() -> PortInt:
    return PortInt(1222)


@pytest.fixture
def run_id() -> RunID:
    return RunID.create()


@pytest.fixture
def request_dns() -> str:
    return "test-endpoint"


@pytest.fixture
def request_scheme() -> str:
    return "http"


@pytest.fixture
def can_save() -> bool:
    return True


@pytest.fixture
def request_simcore_user_agent() -> str:
    return "python/test"


@pytest.fixture
def scheduler_data_from_http_request(
    dynamic_service_create: DynamicServiceCreate,
    simcore_service_labels: SimcoreServiceLabels,
    dynamic_sidecar_port: PortInt,
    request_dns: str,
    request_scheme: str,
    request_simcore_user_agent: str,
    can_save: bool,
    run_id: RunID,
) -> SchedulerData:
    return SchedulerData.from_http_request(
        service=dynamic_service_create,
        simcore_service_labels=simcore_service_labels,
        port=dynamic_sidecar_port,
        request_dns=request_dns,
        request_scheme=request_scheme,
        request_simcore_user_agent=request_simcore_user_agent,
        can_save=can_save,
        run_id=run_id,
    )


@pytest.fixture
def mock_service_inspect(
    scheduler_data_from_http_request: ServiceDetails,
) -> Mapping[str, Any]:
    service_details = json.loads(scheduler_data_from_http_request.model_dump_json())
    service_details["compose_spec"] = json.dumps(service_details["compose_spec"])
    return {
        "Spec": {
            "Labels": {
                DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL: json.dumps(service_details)
            }
        }
    }


@pytest.fixture
def scheduler_data_from_service_inspect(
    mock_service_inspect: Mapping[str, Any]
) -> SchedulerData:
    return SchedulerData.from_service_inspect(mock_service_inspect)


@pytest.fixture(
    params=[
        scheduler_data_from_http_request.__name__,
        scheduler_data_from_service_inspect.__name__,
    ]
)
def scheduler_data(
    scheduler_data_from_http_request: SchedulerData,
    scheduler_data_from_service_inspect: SchedulerData,
    request,
) -> SchedulerData:
    return {
        "scheduler_data_from_http_request": scheduler_data_from_http_request,
        "scheduler_data_from_service_inspect": scheduler_data_from_service_inspect,
    }[request.param]


@pytest.fixture
def cluster_id() -> ClusterID:
    return random.randint(0, 10)


@pytest.fixture(params=list(FileLinkType))
def tasks_file_link_type(request) -> FileLinkType:
    """parametrized fixture on all FileLinkType enum variants"""
    return request.param


# MOCKS the STORAGE service API responses ----------------------------------------


@pytest.fixture
def fake_s3_settings(faker: Faker) -> S3Settings:
    return S3Settings(
        S3_ENDPOINT=faker.url(),
        S3_ACCESS_KEY=faker.uuid4(),
        S3_SECRET_KEY=faker.uuid4(),
        S3_BUCKET_NAME=faker.pystr(),
        S3_REGION=faker.pystr(),
    )


@pytest.fixture
def fake_s3_envs(fake_s3_settings: S3Settings) -> EnvVarsDict:
    return fake_s3_settings.model_dump()


@pytest.fixture
def mocked_storage_service_api(
    fake_s3_settings: S3Settings,
) -> Iterator[respx.MockRouter]:
    settings = AppSettings.create_from_envs()
    assert settings
    assert settings.DIRECTOR_V2_STORAGE

    # pylint: disable=not-context-manager
    with respx.mock(  # type: ignore
        base_url=settings.DIRECTOR_V2_STORAGE.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.post(
            "/simcore-s3:access",
            name="get_or_create_temporary_s3_access",
        ).respond(json=jsonable_encoder({"data": fake_s3_settings}, by_alias=True))

        yield respx_mock


# MOCKS the CATALOG service API responses ----------------------------------------


@pytest.fixture
def mock_service_key_version() -> ServiceKeyVersion:
    return ServiceKeyVersion(
        key=TypeAdapter(ServiceKey).validate_python(
            "simcore/services/dynamic/myservice"
        ),
        version=TypeAdapter(ServiceVersion).validate_python("1.4.5"),
    )


@pytest.fixture
def fake_service_specifications(faker: Faker) -> dict[str, Any]:
    # the service specifications follow the Docker service creation available
    # https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    return {
        "sidecar": DockerServiceSpec.model_validate(
            {
                "Labels": {"label_one": faker.pystr(), "label_two": faker.pystr()},
                "TaskTemplate": {
                    "Placement": {
                        "Constraints": [
                            "node.id==2ivku8v2gvtg4",
                            "node.hostname!=node-2",
                            "node.platform.os==linux",
                            "node.labels.security==high",
                            "engine.labels.operatingsystem==ubuntu-20.04",
                        ]
                    },
                    "Resources": {
                        "Limits": {
                            "NanoCPUs": 16 * 10e9,
                            "MemoryBytes": 10 * 1024**3,
                        },
                        "Reservation": {
                            "NanoCPUs": 136 * 10e9,
                            "MemoryBytes": 312 * 1024**3,
                            "GenericResources": [
                                {
                                    "NamedResourceSpec": {
                                        "Kind": "Chipset",
                                        "Value": "Late2020",
                                    }
                                },
                                {
                                    "DiscreteResourceSpec": {
                                        "Kind": "FAKE_RESOURCE",
                                        "Value": 1 * 1024**3,
                                    }
                                },
                            ],
                        },
                    },
                    "ContainerSpec": {
                        "Command": ["my", "super", "duper", "service", "command"],
                        "Env": [f"SOME_FAKE_ADDITIONAL_ENV={faker.pystr().upper()}"],
                    },
                },
            }
        ).model_dump(by_alias=True, exclude_unset=True)
    }


@pytest.fixture
def mocked_catalog_service_api(
    mock_env: EnvVarsDict,
    mock_service_key_version: ServiceKeyVersion,
    fake_service_specifications: dict[str, Any],
) -> Iterator[respx.MockRouter]:
    settings = AppSettings.create_from_envs()
    assert settings
    assert settings.DIRECTOR_V2_CATALOG

    # pylint: disable=not-context-manager
    with respx.mock(  # type: ignore
        base_url=settings.DIRECTOR_V2_CATALOG.api_base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        # health
        respx_mock.get("/", name="get_health").respond(json="all good ;)")

        # get service specifications
        quoted_key = urllib.parse.quote(mock_service_key_version.key, safe="")
        version = mock_service_key_version.version
        respx_mock.get(
            f"/services/{quoted_key}/{version}/specifications",
            name="get_service_specifications",
        ).respond(json=fake_service_specifications)

        yield respx_mock


@pytest.fixture()
def caplog_info_level(
    caplog: pytest.LogCaptureFixture,
) -> Iterable[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.INFO):
        yield caplog


@pytest.fixture()
def caplog_debug_level(
    caplog: pytest.LogCaptureFixture,
) -> Iterable[pytest.LogCaptureFixture]:
    with caplog.at_level(logging.DEBUG):
        yield caplog


@pytest.fixture
def mock_docker_api(mocker: MockerFixture) -> None:
    module_base = "simcore_service_director_v2.modules.dynamic_sidecar.scheduler"
    mocker.patch(
        f"{module_base}._core._scheduler_utils.get_dynamic_sidecars_to_observe",
        autospec=True,
        return_value=[],
    )
    mocker.patch(
        f"{module_base}._core._observer.are_sidecar_and_proxy_services_present",
        autospec=True,
        return_value=True,
    )
    mocker.patch(
        f"{module_base}._core._scheduler_utils.get_dynamic_sidecar_state",
        return_value=(ServiceState.PENDING, ""),
    )


@pytest.fixture
async def async_docker_client() -> AsyncIterable[aiodocker.Docker]:
    async with aiodocker.Docker() as docker_client:
        yield docker_client

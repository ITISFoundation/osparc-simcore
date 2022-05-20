# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
import random
import urllib.parse
from typing import Any, AsyncIterable, AsyncIterator, Iterator, Mapping

import pytest
import respx
import traitlets.config
from _dask_helpers import DaskGatewayServer
from _pytest.monkeypatch import MonkeyPatch
from dask.distributed import Scheduler, Worker
from dask_gateway_server.app import DaskGateway
from dask_gateway_server.backends.local import UnsafeLocalBackend
from distributed.deploy.spec import SpecCluster
from faker import Faker
from models_library.generated_models.docker_rest_api import (
    ServiceSpec as DockerServiceSpec,
)
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKeyVersion
from pydantic.types import NonNegativeInt
from settings_library.s3 import S3Settings
from simcore_sdk.node_ports_v2 import FileLinkType
from simcore_service_director_v2.core.settings import AppSettings
from simcore_service_director_v2.models.domains.dynamic_services import (
    DynamicServiceCreate,
)
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_SCHEDULER_DATA_LABEL,
)
from simcore_service_director_v2.models.schemas.dynamic_services import (
    SchedulerData,
    ServiceDetails,
)
from yarl import URL


@pytest.fixture
def simcore_services_network_name() -> str:
    return "test_network_name"


@pytest.fixture
def simcore_service_labels() -> SimcoreServiceLabels:
    return SimcoreServiceLabels(
        **SimcoreServiceLabels.Config.schema_extra["examples"][1]
    )


@pytest.fixture
def dynamic_service_create() -> DynamicServiceCreate:
    return DynamicServiceCreate.parse_obj(
        DynamicServiceCreate.Config.schema_extra["example"]
    )


@pytest.fixture(scope="session")
def dynamic_sidecar_port() -> int:
    return 1222


@pytest.fixture
def scheduler_data_from_http_request(
    dynamic_service_create: DynamicServiceCreate,
    simcore_service_labels: SimcoreServiceLabels,
    dynamic_sidecar_port: int,
) -> SchedulerData:
    return SchedulerData.from_http_request(
        service=dynamic_service_create,
        simcore_service_labels=simcore_service_labels,
        port=dynamic_sidecar_port,
    )


@pytest.fixture
def mock_service_inspect(
    scheduler_data_from_http_request: ServiceDetails,
) -> Mapping[str, Any]:
    service_details = json.loads(scheduler_data_from_http_request.json())
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
def cluster_id() -> NonNegativeInt:
    return random.randint(0, 10)


@pytest.fixture
async def dask_spec_local_cluster(
    monkeypatch: MonkeyPatch,
) -> AsyncIterable[SpecCluster]:
    # in this mode we can precisely create a specific cluster
    workers = {
        "cpu-worker": {
            "cls": Worker,
            "options": {
                "nthreads": 2,
                "resources": {"CPU": 2, "RAM": 48e9},
            },
        },
        "gpu-worker": {
            "cls": Worker,
            "options": {
                "nthreads": 1,
                "resources": {
                    "CPU": 1,
                    "GPU": 1,
                    "RAM": 48e9,
                },
            },
        },
        "mpi-worker": {
            "cls": Worker,
            "options": {
                "nthreads": 1,
                "resources": {
                    "CPU": 8,
                    "MPI": 1,
                    "RAM": 768e9,
                },
            },
        },
        "gpu-mpi-worker": {
            "cls": Worker,
            "options": {
                "nthreads": 1,
                "resources": {
                    "GPU": 1,
                    "MPI": 1,
                    "RAM": 768e9,
                },
            },
        },
    }
    scheduler = {"cls": Scheduler}

    async with SpecCluster(
        workers=workers, scheduler=scheduler, asynchronous=True, name="pytest_cluster"
    ) as cluster:
        scheduler_address = URL(cluster.scheduler_address)
        monkeypatch.setenv(
            "COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_URL",
            f"{scheduler_address}" or "invalid",
        )
        yield cluster


@pytest.fixture
def local_dask_gateway_server_config() -> traitlets.config.Config:
    c = traitlets.config.Config()
    c.DaskGateway.backend_class = UnsafeLocalBackend  # type: ignore
    c.DaskGateway.address = "127.0.0.1:0"  # type: ignore
    c.Proxy.address = "127.0.0.1:0"  # type: ignore
    c.DaskGateway.authenticator_class = "dask_gateway_server.auth.SimpleAuthenticator"  # type: ignore
    c.SimpleAuthenticator.password = "qweqwe"  # type: ignore
    c.ClusterConfig.worker_cmd = [  # type: ignore
        "dask-worker",
        "--resources",
        f"CPU=12,GPU=1,MPI=1,RAM={16e9}",
    ]
    # NOTE: This must be set such that the local unsafe backend creates a worker with enough cores/memory
    c.ClusterConfig.worker_cores = 12  # type: ignore
    c.ClusterConfig.worker_memory = "16G"  # type: ignore

    c.DaskGateway.log_level = "DEBUG"  # type: ignore
    return c


@pytest.fixture
async def local_dask_gateway_server(
    local_dask_gateway_server_config: traitlets.config.Config,
) -> AsyncIterator[DaskGatewayServer]:
    print("--> creating local dask gateway server")
    dask_gateway_server = DaskGateway(config=local_dask_gateway_server_config)
    dask_gateway_server.initialize([])  # that is a shitty one!
    print("--> local dask gateway server initialized")
    await dask_gateway_server.setup()
    await dask_gateway_server.backend.proxy._proxy_contacted  # pylint: disable=protected-access

    print("--> local dask gateway server setup completed")
    yield DaskGatewayServer(
        f"http://{dask_gateway_server.backend.proxy.address}",
        f"gateway://{dask_gateway_server.backend.proxy.tcp_address}",
        local_dask_gateway_server_config.SimpleAuthenticator.password,  # type: ignore
        dask_gateway_server,
    )
    print("--> local dask gateway server switching off...")
    await dask_gateway_server.cleanup()
    print("...done")


@pytest.fixture
def fake_s3_settings(faker: Faker) -> S3Settings:
    return S3Settings(
        S3_ENDPOINT=faker.uri(),
        S3_ACCESS_KEY=faker.uuid4(),
        S3_SECRET_KEY=faker.uuid4(),
        S3_ACCESS_TOKEN=faker.uuid4(),
        S3_BUCKET_NAME=faker.pystr(),
    )


@pytest.fixture
def mocked_storage_service_fcts(fake_s3_settings) -> Iterator[respx.MockRouter]:
    settings = AppSettings.create_from_envs()
    with respx.mock(  # type: ignore
        base_url=settings.DIRECTOR_V2_STORAGE.endpoint,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:
        respx_mock.post(
            "/simcore-s3:access",
            name="get_or_create_temporary_s3_access",
        ).respond(json={"data": fake_s3_settings.dict(by_alias=True)})

        yield respx_mock


@pytest.fixture(params=list(FileLinkType))
def tasks_file_link_type(request) -> FileLinkType:
    return request.param


@pytest.fixture
def mock_service_key_version() -> ServiceKeyVersion:
    return ServiceKeyVersion(key="simcore/services/dynamic/myservice", version="1.4.5")


@pytest.fixture
def fake_service_specifications(faker: Faker) -> dict[str, Any]:
    # the service specifications follow the Docker service creation available
    # https://docs.docker.com/engine/api/v1.41/#operation/ServiceCreate
    return {
        "sidecar": DockerServiceSpec.parse_obj(
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
        ).dict(by_alias=True, exclude_unset=True)
    }


@pytest.fixture
def mocked_catalog_service_fcts(
    mock_service_key_version: ServiceKeyVersion,
    fake_service_specifications: dict[str, Any],
) -> Iterator[respx.MockRouter]:
    settings = AppSettings.create_from_envs()
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

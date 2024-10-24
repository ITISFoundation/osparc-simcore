# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from pprint import pformat
from typing import cast

import dask
import dask.config
import distributed
import fsspec
import pytest
import simcore_service_dask_sidecar
from aiobotocore.session import AioBaseClient, get_session
from dask_task_models_library.container_tasks.protocol import TaskOwner
from faker import Faker
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import AnyUrl, TypeAdapter
from pytest_localftpserver.servers import ProcessFTPServer
from pytest_mock.plugin import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.file_utils import _s3fs_settings_from_s3_settings
from yarl import URL

pytest_plugins = [
    "pytest_simcore.aws_server",
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.faker_users_data",
    "pytest_simcore.repository_paths",
]


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # fixtures in pytest_simcore.environs
    service_folder = osparc_simcore_root_dir / "services" / "dask-sidecar"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_dask_sidecar"))
    return service_folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_dask_sidecar.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture
def shared_data_folder(
    tmp_path: Path,
    mocker: MockerFixture,
) -> Path:
    """Emulates shared folder mounted BEFORE app starts"""
    shared_data_folder = tmp_path / "home/scu/computational_shared_data"
    shared_data_folder.mkdir(parents=True, exist_ok=True)

    assert shared_data_folder.exists()

    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_computational_shared_data_mount_point",
        return_value=shared_data_folder,
    )
    return shared_data_folder


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    env_devel_dict: EnvVarsDict,
    shared_data_folder: Path,
) -> EnvVarsDict:
    # configured as worker
    envs = setenvs_from_dict(
        monkeypatch,
        {
            # .env-devel
            **env_devel_dict,
            # Variables directly define inside Dockerfile
            "SC_BOOT_MODE": "debug",
            "SIDECAR_LOGLEVEL": "DEBUG",
            "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME": "simcore_computational_shared_data",
            "SIDECAR_COMP_SERVICES_SHARED_FOLDER": f"{shared_data_folder}",
        },
    )

    # Variables  passed upon start via services/docker-compose.yml file under dask-sidecar/scheduler
    monkeypatch.delenv("DASK_START_AS_SCHEDULER", raising=False)

    return envs


@pytest.fixture
def local_cluster(app_environment: EnvVarsDict) -> Iterator[distributed.LocalCluster]:
    print(pformat(dask.config.get("distributed")))
    with distributed.LocalCluster(
        worker_class=distributed.Worker,
        resources={"CPU": 10, "GPU": 10},
        preload="simcore_service_dask_sidecar.tasks",
    ) as cluster:
        assert cluster
        assert isinstance(cluster, distributed.LocalCluster)
        yield cluster


@pytest.fixture
def dask_client(
    local_cluster: distributed.LocalCluster,
) -> Iterator[distributed.Client]:
    with distributed.Client(local_cluster) as client:
        yield client


@pytest.fixture
async def async_local_cluster(
    app_environment: EnvVarsDict,
) -> AsyncIterator[distributed.LocalCluster]:
    print(pformat(dask.config.get("distributed")))
    async with distributed.LocalCluster(
        worker_class=distributed.Worker,
        resources={"CPU": 10, "GPU": 10},
        preload="simcore_service_dask_sidecar.tasks",
        asynchronous=True,
    ) as cluster:
        assert cluster
        assert isinstance(cluster, distributed.LocalCluster)
        yield cluster


@pytest.fixture
async def async_dask_client(
    async_local_cluster: distributed.LocalCluster,
) -> AsyncIterator[distributed.Client]:
    async with distributed.Client(async_local_cluster, asynchronous=True) as client:
        yield client


@pytest.fixture(scope="module")
def ftp_server(ftpserver: ProcessFTPServer) -> list[URL]:
    faker = Faker()

    files = ["file_1", "file_2", "file_3"]
    ftp_server_base_url = ftpserver.get_login_data(style="url")
    list_of_file_urls = [f"{ftp_server_base_url}/{filename}.txt" for filename in files]
    with fsspec.open_files(list_of_file_urls, "wt") as open_files:
        for index, fp in enumerate(open_files):
            fp.write(f"This is the file contents of '{files[index]}'\n")
            for s in faker.sentences():
                fp.write(f"{s}\n")

    return [URL(f) for f in list_of_file_urls]


@pytest.fixture
def s3_settings(mocked_s3_server_envs: None) -> S3Settings:
    return S3Settings.create_from_envs()


@pytest.fixture
def s3_endpoint_url(s3_settings: S3Settings) -> AnyUrl:
    assert s3_settings.S3_ENDPOINT
    return TypeAdapter(AnyUrl).validate_python(
        f"{s3_settings.S3_ENDPOINT}",
    )


@pytest.fixture
async def aiobotocore_s3_client(
    s3_settings: S3Settings, s3_endpoint_url: AnyUrl
) -> AsyncIterator[AioBaseClient]:
    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=f"{s3_endpoint_url}",
        aws_secret_access_key="xxx",  # noqa: S106
        aws_access_key_id="xxx",
    ) as client:
        yield client


@pytest.fixture
async def bucket(
    aiobotocore_s3_client: AioBaseClient, s3_settings: S3Settings
) -> AsyncIterator[str]:
    response = await aiobotocore_s3_client.create_bucket(
        Bucket=s3_settings.S3_BUCKET_NAME
    )
    assert "ResponseMetadata" in response
    assert "HTTPStatusCode" in response["ResponseMetadata"]
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    response = await aiobotocore_s3_client.list_buckets()
    assert response["Buckets"]
    assert len(response["Buckets"]) == 1
    return response["Buckets"][0]["Name"]


@pytest.fixture
def s3_remote_file_url(s3_settings: S3Settings, faker: Faker) -> Callable[..., AnyUrl]:
    def creator(file_path: Path | None = None) -> AnyUrl:
        file_path_with_bucket = Path(s3_settings.S3_BUCKET_NAME) / (
            file_path or faker.file_name()
        )
        return TypeAdapter(AnyUrl).validate_python(f"s3://{file_path_with_bucket}")

    return creator


@pytest.fixture
def file_on_s3_server(
    s3_settings: S3Settings,
    s3_remote_file_url: Callable[..., AnyUrl],
    faker: Faker,
) -> Iterator[Callable[..., AnyUrl]]:
    list_of_created_files: list[AnyUrl] = []
    s3_storage_kwargs = _s3fs_settings_from_s3_settings(s3_settings)

    def creator() -> AnyUrl:
        new_remote_file = s3_remote_file_url()
        open_file = fsspec.open(f"{new_remote_file}", mode="wt", **s3_storage_kwargs)
        with open_file as fp:
            fp.write(  # type: ignore
                f"This is the file contents of file #'{(len(list_of_created_files)+1):03}'\n"
            )
            for s in faker.sentences(5):
                fp.write(f"{s}\n")  # type: ignore
        list_of_created_files.append(new_remote_file)
        return new_remote_file

    yield creator

    # cleanup
    fs = fsspec.filesystem("s3", **s3_storage_kwargs)
    for file in list_of_created_files:
        fs.delete(f"{file}".partition(f"{file.scheme}://")[2])


@pytest.fixture
def job_id() -> str:
    return "some_incredible_string"


@pytest.fixture
def project_id(faker: Faker) -> ProjectID:
    return cast(ProjectID, faker.uuid4(cast_to=None))


@pytest.fixture
def node_id(faker: Faker) -> NodeID:
    return cast(NodeID, faker.uuid4(cast_to=None))


@pytest.fixture(params=["no_parent_node", "with_parent_node"])
def task_owner(
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    request: pytest.FixtureRequest,
    faker: Faker,
) -> TaskOwner:
    return TaskOwner(
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        parent_project_id=(
            None
            if request.param == "no_parent_node"
            else cast(ProjectID, faker.uuid4(cast_to=None))
        ),
        parent_node_id=(
            None
            if request.param == "no_parent_node"
            else cast(NodeID, faker.uuid4(cast_to=None))
        ),
    )

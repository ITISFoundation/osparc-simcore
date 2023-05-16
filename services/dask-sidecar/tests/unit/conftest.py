# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from pathlib import Path
from pprint import pformat
from typing import AsyncIterator, Callable, Iterable, Iterator

import dask
import distributed
import fsspec
import pytest
import simcore_service_dask_sidecar
from aiobotocore.session import AioBaseClient, get_session
from faker import Faker
from pydantic import AnyUrl, parse_obj_as
from pytest import MonkeyPatch, TempPathFactory
from pytest_localftpserver.servers import ProcessFTPServer
from pytest_mock.plugin import MockerFixture
from settings_library.s3 import S3Settings
from simcore_service_dask_sidecar.file_utils import _s3fs_settings_from_s3_settings
from yarl import URL

pytest_plugins = [
    "pytest_simcore.aws_services",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
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


@pytest.fixture()
def mock_service_envs(
    mock_env_devel_environment: dict[str, str | None],
    monkeypatch: MonkeyPatch,
    mocker: MockerFixture,
    tmp_path_factory: TempPathFactory,
) -> None:
    # Variables directly define inside Dockerfile
    monkeypatch.setenv("SC_BOOT_MODE", "debug-ptvsd")

    monkeypatch.setenv("SIDECAR_LOGLEVEL", "DEBUG")
    monkeypatch.setenv(
        "SIDECAR_COMP_SERVICES_SHARED_VOLUME_NAME", "simcore_computational_shared_data"
    )

    shared_data_folder = tmp_path_factory.mktemp("pytest_comp_shared_data")
    assert shared_data_folder.exists()
    monkeypatch.setenv("SIDECAR_COMP_SERVICES_SHARED_FOLDER", f"{shared_data_folder}")
    mocker.patch(
        "simcore_service_dask_sidecar.computational_sidecar.core.get_computational_shared_data_mount_point",
        return_value=shared_data_folder,
    )


@pytest.fixture
def dask_client(mock_service_envs: None) -> Iterable[distributed.Client]:
    print(pformat(dask.config.get("distributed")))
    with distributed.LocalCluster(
        worker_class=distributed.Worker,
        **{
            "resources": {"CPU": 10, "GPU": 10},
            "preload": "simcore_service_dask_sidecar.tasks",
        },
    ) as cluster:
        with distributed.Client(cluster) as client:
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
    return parse_obj_as(
        AnyUrl,
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
        aws_secret_access_key="xxx",
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
    bucket_name = response["Buckets"][0]["Name"]
    yield bucket_name
    # await _clean_bucket_content(aiobotocore_s3_client, bucket_name)


@pytest.fixture
def s3_remote_file_url(s3_settings: S3Settings, faker: Faker) -> Callable[..., AnyUrl]:
    def creator(file_path: Path | None = None) -> AnyUrl:
        file_path_with_bucket = Path(s3_settings.S3_BUCKET_NAME) / (
            file_path or faker.file_name()
        )
        return parse_obj_as(AnyUrl, f"s3://{file_path_with_bucket}")

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
        open_file = fsspec.open(new_remote_file, mode="wt", **s3_storage_kwargs)
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
        fs.delete(file.partition(f"{file.scheme}://")[2])

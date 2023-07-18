# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=unsupported-assignment-operation
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import sys
import urllib.parse
import uuid
from pathlib import Path
from time import perf_counter
from typing import AsyncIterator, Awaitable, Callable, Iterator, cast

import dotenv
import pytest
import simcore_service_storage
from aiobotocore.session import get_session
from aiohttp import web
from aiohttp.test_utils import TestClient, unused_port
from aiopg.sa import Engine
from aioresponses import aioresponses as AioResponsesMock
from faker import Faker
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadSchema,
    PresignedLink,
    UploadedPart,
)
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from moto.server import ThreadedMotoServer
from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_docker import get_localhost_ip
from simcore_postgres_database.storage_models import file_meta_data, projects, users
from simcore_service_storage.application import create
from simcore_service_storage.dsm import get_dsm_provider
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3 import get_s3_client
from simcore_service_storage.s3_client import StorageS3Client
from simcore_service_storage.settings import Settings
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from tests.helpers.file_utils import upload_file_to_presigned_link
from tests.helpers.utils_file_meta_data import assert_file_meta_data_in_db
from yarl import URL

pytest_plugins = [
    "pytest_simcore.aioresponses_mocker",
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.file_extra",
    "pytest_simcore.httpbin_service",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
    "pytest_simcore.tmp_path_extra",
    "tests.fixtures.data_models",
    "tests.fixtures.datcore_adapter",
]

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# TODO: replace by pytest_simcore
sys.path.append(str(CURRENT_DIR / "helpers"))


@pytest.fixture(scope="session")
def here() -> Path:
    return CURRENT_DIR


@pytest.fixture(scope="session")
def package_dir(here) -> Path:
    dirpath = Path(simcore_service_storage.__file__).parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(here) -> Path:
    root_dir = here.parent.parent.parent
    assert root_dir.exists() and any(
        root_dir.glob("services")
    ), "Is this service within osparc-simcore repo?"
    return root_dir


@pytest.fixture(scope="session")
def osparc_api_specs_dir(osparc_simcore_root_dir) -> Path:
    dirpath = osparc_simcore_root_dir / "api" / "specs"
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir) -> Path:
    # uses pytest_simcore.environs.osparc_simcore_root_dir
    service_folder = osparc_simcore_root_dir / "services" / "storage"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_storage"))
    return service_folder


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> dict:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    environ = dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)
    return environ


@pytest.fixture(scope="function")
def project_env_devel_environment(project_env_devel_dict, monkeypatch) -> None:
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)


## FAKE DATA FIXTURES ----------------------------------------------


@pytest.fixture(scope="function")
def mock_files_factory(tmpdir_factory) -> Callable[[int], list[Path]]:
    def _create_files(count: int) -> list[Path]:
        filepaths = []
        for _i in range(count):
            filepath = Path(tmpdir_factory.mktemp("data")) / f"{uuid.uuid4()}.txt"
            filepath.write_text("Hello world\n")
            filepaths.append(filepath)

        return filepaths

    return _create_files


@pytest.fixture
async def cleanup_user_projects_file_metadata(aiopg_engine: Engine):
    yield
    # cleanup
    async with aiopg_engine.acquire() as conn:
        await conn.execute(file_meta_data.delete())
        await conn.execute(projects.delete())
        await conn.execute(users.delete())


@pytest.fixture
def simcore_s3_dsm(client) -> SimcoreS3DataManager:
    return cast(
        SimcoreS3DataManager,
        get_dsm_provider(client.app).get(SimcoreS3DataManager.get_location_id()),
    )


@pytest.fixture(scope="module")
def mocked_s3_server() -> Iterator[ThreadedMotoServer]:
    """creates a moto-server that emulates AWS services in place
    NOTE: Never use a bucket with underscores it fails!!
    """
    server = ThreadedMotoServer(ip_address=get_localhost_ip(), port=unused_port())
    # pylint: disable=protected-access
    print(f"--> started mock S3 server on {server._ip_address}:{server._port}")
    print(
        f"--> Dashboard available on [http://{server._ip_address}:{server._port}/moto-api/]"
    )
    server.start()
    yield server
    server.stop()
    print(f"<-- stopped mock S3 server on {server._ip_address}:{server._port}")


@pytest.fixture
async def mocked_s3_server_envs(
    mocked_s3_server: ThreadedMotoServer, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("S3_SECURE", "false")
    monkeypatch.setenv(
        "S3_ENDPOINT",
        f"{mocked_s3_server._ip_address}:{mocked_s3_server._port}",  # pylint: disable=protected-access
    )
    monkeypatch.setenv("S3_ACCESS_KEY", "xxx")
    monkeypatch.setenv("S3_SECRET_KEY", "xxx")
    monkeypatch.setenv("S3_BUCKET_NAME", "pytestbucket")

    yield

    # cleanup the buckets
    session = get_session()
    async with session.create_client(
        "s3",
        endpoint_url=f"http://{mocked_s3_server._ip_address}:{mocked_s3_server._port}",  # pylint: disable=protected-access
        aws_secret_access_key="xxx",
        aws_access_key_id="xxx",
    ) as client:
        await _remove_all_buckets(client)


async def _clean_bucket_content(aiobotore_s3_client, bucket: S3BucketName):
    response = await aiobotore_s3_client.list_objects_v2(Bucket=bucket)
    while response["KeyCount"] > 0:
        await aiobotore_s3_client.delete_objects(
            Bucket=bucket,
            Delete={
                "Objects": [
                    {"Key": obj["Key"]} for obj in response["Contents"] if "Key" in obj
                ]
            },
        )
        response = await aiobotore_s3_client.list_objects_v2(Bucket=bucket)


async def _remove_all_buckets(aiobotore_s3_client):
    response = await aiobotore_s3_client.list_buckets()
    bucket_names = [
        bucket["Name"] for bucket in response["Buckets"] if "Name" in bucket
    ]
    await asyncio.gather(
        *(_clean_bucket_content(aiobotore_s3_client, bucket) for bucket in bucket_names)
    )
    await asyncio.gather(
        *(aiobotore_s3_client.delete_bucket(Bucket=bucket) for bucket in bucket_names)
    )


@pytest.fixture
async def storage_s3_client(
    client: TestClient,
) -> StorageS3Client:
    assert client.app
    return get_s3_client(client.app)


@pytest.fixture
async def storage_s3_bucket(app_settings: Settings) -> str:
    assert app_settings.STORAGE_S3
    return app_settings.STORAGE_S3.S3_BUCKET_NAME


@pytest.fixture
def mock_config(
    aiopg_engine: Engine,
    postgres_host_config: dict[str, str],
    mocked_s3_server_envs,
    datcore_adapter_service_mock: AioResponsesMock,
):
    # NOTE: this can be overriden in tests that do not need all dependencies up
    ...


@pytest.fixture
def app_settings(mock_config) -> Settings:
    test_app_settings = Settings.create_from_envs()
    print(f"{test_app_settings.json(indent=2)=}")
    return test_app_settings


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable[..., int],
    app_settings: Settings,
) -> TestClient:
    app = create(app_settings)
    return event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": unused_tcp_port_factory()})
    )


@pytest.fixture
async def node_id(
    project_id: ProjectID, create_project_node: Callable[[ProjectID], Awaitable[NodeID]]
) -> NodeID:
    return await create_project_node(project_id)


@pytest.fixture
def simcore_file_id(
    project_id: ProjectID,
    node_id: NodeID,
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    faker: Faker,
) -> SimcoreS3FileID:
    return create_simcore_file_id(
        project_id,
        node_id,
        f"some_folder/another/öä$äö2-34 name in to add complexity {faker.file_name()}",
    )


# NOTE: this will be enabled at a later timepoint
@pytest.fixture(
    params=[
        SimcoreS3DataManager.get_location_id(),
        # DatCoreDataManager.get_location_id(),
    ],
    ids=[
        SimcoreS3DataManager.get_location_name(),
        # DatCoreDataManager.get_location_name(),
    ],
)
def location_id(request: pytest.FixtureRequest) -> LocationID:
    return request.param  # type: ignore


@pytest.fixture
async def get_file_meta_data(
    client: TestClient, user_id: UserID, location_id: LocationID
) -> Callable[..., Awaitable[FileMetaDataGet]]:
    async def _getter(file_id: SimcoreS3FileID) -> FileMetaDataGet:
        assert client.app
        url = (
            client.app.router["get_file_metadata"]
            .url_for(
                location_id=f"{location_id}",
                file_id=urllib.parse.quote(file_id, safe=""),
            )
            .with_query(user_id=user_id)
        )
        response = await client.get(f"{url}")
        data, error = await assert_status(response, web.HTTPOk)
        assert not error
        assert data
        received_fmd = parse_obj_as(FileMetaDataGet, data)
        assert received_fmd
        print(f"<-- {received_fmd.json(indent=2)=}")
        return received_fmd

    return _getter


@pytest.fixture
async def create_upload_file_link_v1(
    client: TestClient, user_id: UserID, location_id: LocationID
) -> AsyncIterator[Callable[..., Awaitable[PresignedLink]]]:
    file_params: list[tuple[UserID, int, SimcoreS3FileID]] = []

    async def _link_creator(file_id: SimcoreS3FileID, **query_kwargs) -> PresignedLink:
        assert client.app
        url = (
            client.app.router["upload_file"]
            .url_for(
                location_id=f"{location_id}",
                file_id=urllib.parse.quote(file_id, safe=""),
            )
            .with_query(**query_kwargs, user_id=user_id)
        )
        assert (
            "file_size" not in url.query
        ), "v1 call to upload_file MUST NOT contain file_size field, this is reserved for v2 call"
        response = await client.put(f"{url}")
        data, error = await assert_status(response, web.HTTPOk)
        assert not error
        assert data
        received_file_upload_link = parse_obj_as(PresignedLink, data)
        assert received_file_upload_link
        print(f"--> created link for {file_id=}")
        file_params.append((user_id, location_id, file_id))
        return received_file_upload_link

    yield _link_creator

    # cleanup
    assert client.app
    clean_tasks = []
    for u_id, loc_id, file_id in file_params:
        url = (
            client.app.router["delete_file"]
            .url_for(
                location_id=f"{loc_id}",
                file_id=urllib.parse.quote(file_id, safe=""),
            )
            .with_query(user_id=u_id)
        )
        clean_tasks.append(client.delete(f"{url}"))
    await asyncio.gather(*clean_tasks)


@pytest.fixture
async def create_upload_file_link_v2(
    client: TestClient, user_id: UserID, location_id: LocationID
) -> AsyncIterator[Callable[..., Awaitable[FileUploadSchema]]]:
    file_params: list[tuple[UserID, int, SimcoreS3FileID]] = []

    async def _link_creator(
        file_id: SimcoreS3FileID, **query_kwargs
    ) -> FileUploadSchema:
        assert client.app
        url = (
            client.app.router["upload_file"]
            .url_for(
                location_id=f"{location_id}",
                file_id=urllib.parse.quote(file_id, safe=""),
            )
            .with_query(**query_kwargs, user_id=user_id)
        )
        assert (
            "file_size" in url.query
        ), "V2 call to upload file must contain file_size field!"
        response = await client.put(f"{url}")
        data, error = await assert_status(response, web.HTTPOk)
        assert not error
        assert data
        received_file_upload = parse_obj_as(FileUploadSchema, data)
        assert received_file_upload
        print(f"--> created link for {file_id=}")
        file_params.append((user_id, location_id, file_id))
        return received_file_upload

    yield _link_creator

    # cleanup
    assert client.app
    clean_tasks = []
    for u_id, loc_id, file_id in file_params:
        url = (
            client.app.router["delete_file"]
            .url_for(
                location_id=f"{loc_id}",
                file_id=urllib.parse.quote(file_id, safe=""),
            )
            .with_query(user_id=u_id)
        )
        clean_tasks.append(client.delete(f"{url}"))
    await asyncio.gather(*clean_tasks)


@pytest.fixture
def upload_file(
    aiopg_engine: Engine,
    storage_s3_client: StorageS3Client,
    storage_s3_bucket: S3BucketName,
    client: TestClient,
    project_id: ProjectID,
    node_id: NodeID,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
) -> Callable[
    [ByteSize, str, SimcoreS3FileID | None], Awaitable[tuple[Path, SimcoreS3FileID]]
]:
    async def _uploader(
        file_size: ByteSize,
        file_name: str,
        file_id: SimcoreS3FileID | None = None,
        wait_for_completion: bool = True,
    ) -> tuple[Path, SimcoreS3FileID]:
        assert client.app
        # create a file
        file = create_file_of_size(file_size, file_name)
        if not file_id:
            file_id = create_simcore_file_id(project_id, node_id, file_name)
        # get an upload link
        file_upload_link = await create_upload_file_link_v2(
            file_id, link_type="presigned", file_size=file_size
        )

        # upload the file
        part_to_etag: list[UploadedPart] = await upload_file_to_presigned_link(
            file, file_upload_link
        )
        # complete the upload
        complete_url = URL(file_upload_link.links.complete_upload).relative()
        start = perf_counter()
        print(f"--> completing upload of {file=}")
        response = await client.post(
            f"{complete_url}",
            json=jsonable_encoder(FileUploadCompletionBody(parts=part_to_etag)),
        )
        response.raise_for_status()
        data, error = await assert_status(response, web.HTTPAccepted)
        assert not error
        assert data
        file_upload_complete_response = FileUploadCompleteResponse.parse_obj(data)
        state_url = URL(file_upload_complete_response.links.state).relative()

        if not wait_for_completion:
            # we do not want to wait for completion to finish
            return file, file_id, state_url

        completion_etag = None
        async for attempt in AsyncRetrying(
            reraise=True,
            wait=wait_fixed(1),
            stop=stop_after_delay(60),
            retry=retry_if_exception_type(ValueError),
        ):
            with attempt:
                print(
                    f"--> checking for upload {state_url=}, {attempt.retry_state.attempt_number}..."
                )
                response = await client.post(f"{state_url}")
                response.raise_for_status()
                data, error = await assert_status(response, web.HTTPOk)
                assert not error
                assert data
                future = FileUploadCompleteFutureResponse.parse_obj(data)
                if future.state == FileUploadCompleteState.NOK:
                    raise ValueError(f"{data=}")
                assert future.state == FileUploadCompleteState.OK
                assert future.e_tag is not None
                completion_etag = future.e_tag
                print(
                    f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]"
                )

        print(f"--> completed upload in {perf_counter() - start}")

        # check the entry in db now has the correct file size, and the upload id is gone
        await assert_file_meta_data_in_db(
            aiopg_engine,
            file_id=file_id,
            expected_entry_exists=True,
            expected_file_size=file_size,
            expected_upload_id=False,
            expected_upload_expiration_date=False,
        )
        # check the file is in S3 for real
        s3_metadata = await storage_s3_client.get_file_metadata(
            storage_s3_bucket, file_id
        )
        assert s3_metadata.size == file_size
        assert s3_metadata.last_modified
        assert s3_metadata.e_tag == completion_etag
        return file, file_id

    return _uploader


@pytest.fixture
def create_simcore_file_id(
    faker: Faker,
) -> Callable[[ProjectID, NodeID, str, Path | None], SimcoreS3FileID]:
    def _creator(
        project_id: ProjectID,
        node_id: NodeID,
        file_name: str,
        file_base_path: Path | None = None,
    ) -> SimcoreS3FileID:
        s3_file_name = file_name
        if file_base_path:
            s3_file_name = f"{file_base_path / file_name}"
        clean_path = Path(f"{project_id}/{node_id}/{s3_file_name}")
        return SimcoreS3FileID(f"{clean_path}")

    return _creator

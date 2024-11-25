# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=unsupported-assignment-operation
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import logging
import sys
import urllib.parse
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import cast

import aioresponses
import dotenv
import pytest
import simcore_service_storage
from aiohttp.test_utils import TestClient
from aiopg.sa import Engine
from aws_library.s3 import SimcoreS3API
from faker import Faker
from fakeredis.aioredis import FakeRedis
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadSchema,
    UploadedPart,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.s3 import upload_file_to_presigned_link
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from settings_library.s3 import S3Settings
from simcore_postgres_database.storage_models import file_meta_data, projects, users
from simcore_service_storage.application import create
from simcore_service_storage.dsm import get_dsm_provider
from simcore_service_storage.handlers_files import UPLOAD_TASKS_KEY
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.s3 import get_s3_client
from simcore_service_storage.settings import Settings
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from tests.helpers.utils_file_meta_data import assert_file_meta_data_in_db
from types_aiobotocore_s3 import S3Client
from yarl import URL

pytest_plugins = [
    "pytest_simcore.aioresponses_mocker",
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
    "pytest_simcore.cli_runner",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.file_extra",
    "pytest_simcore.httpbin_service",
    "pytest_simcore.minio_service",
    "pytest_simcore.openapi_specs",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.repository_paths",
    "tests.fixtures.data_models",
    "tests.fixtures.datcore_adapter",
]

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

sys.path.append(str(CURRENT_DIR / "helpers"))


@pytest.fixture(scope="session")
def here() -> Path:
    return CURRENT_DIR


@pytest.fixture(scope="session")
def package_dir(here: Path) -> Path:
    dirpath = Path(simcore_service_storage.__file__).parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def project_slug_dir(osparc_simcore_root_dir: Path) -> Path:
    # uses pytest_simcore.environs.osparc_simcore_root_dir
    service_folder = osparc_simcore_root_dir / "services" / "storage"
    assert service_folder.exists()
    assert any(service_folder.glob("src/simcore_service_storage"))
    return service_folder


@pytest.fixture(scope="session")
def project_env_devel_dict(project_slug_dir: Path) -> dict[str, str | None]:
    env_devel_file = project_slug_dir / ".env-devel"
    assert env_devel_file.exists()
    return dotenv.dotenv_values(env_devel_file, verbose=True, interpolate=True)


@pytest.fixture
def project_env_devel_environment(
    project_env_devel_dict: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    for key, value in project_env_devel_dict.items():
        monkeypatch.setenv(key, value)


## FAKE DATA FIXTURES ----------------------------------------------


@pytest.fixture
async def cleanup_user_projects_file_metadata(aiopg_engine: Engine):
    yield
    # cleanup
    async with aiopg_engine.acquire() as conn:
        await conn.execute(file_meta_data.delete())
        await conn.execute(projects.delete())
        await conn.execute(users.delete())


@pytest.fixture
def simcore_s3_dsm(client: TestClient) -> SimcoreS3DataManager:
    assert client.app
    return cast(
        SimcoreS3DataManager,
        get_dsm_provider(client.app).get(SimcoreS3DataManager.get_location_id()),
    )


@pytest.fixture
async def storage_s3_client(
    client: TestClient,
) -> SimcoreS3API:
    assert client.app
    return get_s3_client(client.app)


@pytest.fixture
async def storage_s3_bucket(app_settings: Settings) -> str:
    assert app_settings.STORAGE_S3
    return app_settings.STORAGE_S3.S3_BUCKET_NAME


@pytest.fixture
def app_settings(
    aiopg_engine: Engine,
    postgres_host_config: dict[str, str],
    mocked_s3_server_envs: EnvVarsDict,
    external_envfile_dict: EnvVarsDict,
    datcore_adapter_service_mock: aioresponses.aioresponses,
    monkeypatch: pytest.MonkeyPatch,
) -> Settings:
    s3_settings_dict = {}
    if external_envfile_dict:
        s3_settings = S3Settings.create_from_envs(**external_envfile_dict)
        if s3_settings.S3_ENDPOINT is None:
            monkeypatch.delenv("S3_ENDPOINT")
            s3_settings_dict = s3_settings.model_dump(exclude={"S3_ENDPOINT"})
        else:
            s3_settings_dict = s3_settings.model_dump()
    setenvs_from_dict(
        monkeypatch,
        {
            **s3_settings_dict,
            "STORAGE_TRACING": "null",
        },
    )
    test_app_settings = Settings.create_from_envs()
    print(f"{test_app_settings.model_dump_json(indent=2)=}")
    return test_app_settings


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable[..., int],
    app_settings: Settings,
    mocked_redis_server,
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
        data, error = await assert_status(response, status.HTTP_200_OK)
        assert not error
        assert data
        received_fmd = TypeAdapter(FileMetaDataGet).validate_python(data)
        assert received_fmd
        return received_fmd

    return _getter


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
        data, error = await assert_status(response, status.HTTP_200_OK)
        assert not error
        assert data
        received_file_upload = TypeAdapter(FileUploadSchema).validate_python(data)
        assert received_file_upload
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
    storage_s3_client: SimcoreS3API,
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
        sha256_checksum: SHA256Str | None = None,
        project_id: ProjectID = project_id,
    ) -> tuple[Path, SimcoreS3FileID]:
        assert client.app
        # create a file
        file = create_file_of_size(file_size, file_name)
        if not file_id:
            file_id = create_simcore_file_id(project_id, node_id, file_name)
        # get an upload link
        query_params: dict = {}
        if sha256_checksum:
            query_params["sha256_checksum"] = f"{sha256_checksum}"
        file_upload_link = await create_upload_file_link_v2(
            file_id, link_type="presigned", file_size=file_size, **query_params
        )

        # upload the file
        part_to_etag: list[UploadedPart] = await upload_file_to_presigned_link(
            file, file_upload_link
        )
        # complete the upload
        complete_url = URL(f"{file_upload_link.links.complete_upload}").relative()
        with log_context(logging.INFO, f"completing upload of {file=}"):
            response = await client.post(
                f"{complete_url}",
                json=jsonable_encoder(FileUploadCompletionBody(parts=part_to_etag)),
            )
            response.raise_for_status()
            data, error = await assert_status(response, status.HTTP_202_ACCEPTED)
            assert not error
            assert data
            file_upload_complete_response = FileUploadCompleteResponse.model_validate(
                data
            )
            state_url = URL(f"{file_upload_complete_response.links.state}").relative()

            completion_etag = None
            async for attempt in AsyncRetrying(
                reraise=True,
                wait=wait_fixed(1),
                stop=stop_after_delay(60),
                retry=retry_if_exception_type(ValueError),
            ):
                with attempt, log_context(
                    logging.INFO,
                    f"waiting for upload completion {state_url=}, {attempt.retry_state.attempt_number}",
                ) as ctx:
                    response = await client.post(f"{state_url}")
                    response.raise_for_status()
                    data, error = await assert_status(response, status.HTTP_200_OK)
                    assert not error
                    assert data
                    future = FileUploadCompleteFutureResponse.model_validate(data)
                    if future.state == FileUploadCompleteState.NOK:
                        msg = f"{data=}"
                        raise ValueError(msg)
                    assert future.state == FileUploadCompleteState.OK
                    assert future.e_tag is not None
                    completion_etag = future.e_tag
                    ctx.logger.info(
                        "%s",
                        f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]",
                    )

        # check the entry in db now has the correct file size, and the upload id is gone
        await assert_file_meta_data_in_db(
            aiopg_engine,
            file_id=file_id,
            expected_entry_exists=True,
            expected_file_size=file_size,
            expected_upload_id=False,
            expected_upload_expiration_date=False,
            expected_sha256_checksum=sha256_checksum,
        )
        # check the file is in S3 for real
        s3_metadata = await storage_s3_client.get_object_metadata(
            bucket=storage_s3_bucket, object_key=file_id
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
        return TypeAdapter(SimcoreS3FileID).validate_python(f"{clean_path}")

    return _creator


@pytest.fixture
async def with_versioning_enabled(
    s3_client: S3Client,
    storage_s3_bucket: S3BucketName,
) -> None:
    await s3_client.put_bucket_versioning(
        Bucket=storage_s3_bucket,
        VersioningConfiguration={"MFADelete": "Disabled", "Status": "Enabled"},
    )


@pytest.fixture
async def create_empty_directory(
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    client: TestClient,
    project_id: ProjectID,
    node_id: NodeID,
) -> Callable[..., Awaitable[FileUploadSchema]]:
    async def _directory_creator(dir_name: str):
        # creating an empty directory goes through the same procedure as uploading a multipart file
        # done by using 3 calls:
        # 1. create the link as a directory
        # 2. call complete_upload link
        # 3. call file_upload_complete_response until it replies OK

        directory_file_id = create_simcore_file_id(project_id, node_id, dir_name)
        directory_file_upload: FileUploadSchema = await create_upload_file_link_v2(
            directory_file_id, link_type="s3", is_directory="true", file_size=-1
        )
        # always returns a v2 link when dealing with directories
        assert isinstance(directory_file_upload, FileUploadSchema)
        assert len(directory_file_upload.urls) == 1

        # complete the upload
        complete_url = URL(f"{directory_file_upload.links.complete_upload}").relative()
        response = await client.post(
            f"{complete_url}",
            json=jsonable_encoder(FileUploadCompletionBody(parts=[])),
        )
        response.raise_for_status()
        data, error = await assert_status(response, status.HTTP_202_ACCEPTED)
        assert not error
        assert data
        file_upload_complete_response = FileUploadCompleteResponse.model_validate(data)
        state_url = URL(f"{file_upload_complete_response.links.state}").relative()

        # check that it finished updating
        assert client.app
        client.app[UPLOAD_TASKS_KEY].clear()
        # now check for the completion
        async for attempt in AsyncRetrying(
            reraise=True,
            wait=wait_fixed(1),
            stop=stop_after_delay(60),
            retry=retry_if_exception_type(AssertionError),
        ):
            with attempt, log_context(
                logging.INFO,
                f"waiting for upload completion {state_url=}, {attempt.retry_state.attempt_number}",
            ) as ctx:
                response = await client.post(f"{state_url}")
                data, error = await assert_status(response, status.HTTP_200_OK)
                assert not error
                assert data
                future = FileUploadCompleteFutureResponse.model_validate(data)
                assert future.state == FileUploadCompleteState.OK
                assert future.e_tag is None
                ctx.logger.info(
                    "%s",
                    f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]",
                )

        return directory_file_upload

    return _directory_creator


@pytest.fixture
async def populate_directory(
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    project_id: ProjectID,
    node_id: NodeID,
) -> Callable[..., Awaitable[None]]:
    async def _create_content(
        file_size_in_dir: ByteSize,
        dir_name: str,
        subdir_count: int = 4,
        file_count: int = 5,
    ) -> None:
        file = create_file_of_size(file_size_in_dir, "some_file")

        async def _create_file(s: int, f: int):
            file_name = f"{dir_name}/sub-dir-{s}/file-{f}"
            clean_path = Path(f"{project_id}/{node_id}/{file_name}")
            await storage_s3_client.upload_file(
                bucket=storage_s3_bucket,
                file=file,
                object_key=TypeAdapter(SimcoreS3FileID).validate_python(
                    f"{clean_path}"
                ),
                bytes_transfered_cb=None,
            )

        tasks = [
            _create_file(s, f) for f in range(file_count) for s in range(subdir_count)
        ]

        await asyncio.gather(*tasks)

        file.unlink()

    return _create_content


@pytest.fixture
async def delete_directory(
    client: TestClient,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    user_id: UserID,
    location_id: LocationID,
) -> Callable[..., Awaitable[None]]:
    async def _dir_remover(directory_file_upload: FileUploadSchema) -> None:
        assert directory_file_upload.urls[0].path
        directory_file_id = directory_file_upload.urls[0].path.strip("/")
        assert client.app
        delete_url = (
            client.app.router["delete_file"]
            .url_for(
                location_id=f"{location_id}",
                file_id=urllib.parse.quote(directory_file_id, safe=""),
            )
            .with_query(user_id=user_id)
        )
        response = await client.delete(f"{delete_url}")
        await assert_status(response, status.HTTP_204_NO_CONTENT)

        # NOTE: ensures no more files are left in the directory,
        # even if one file is left this will detect it
        list_files_metadata_url = (
            client.app.router["get_files_metadata"]
            .url_for(location_id=f"{location_id}")
            .with_query(user_id=user_id, uuid_filter=directory_file_id)
        )
        response = await client.get(f"{list_files_metadata_url}")
        data, error = await assert_status(response, status.HTTP_200_OK)
        assert error is None
        assert data == []

    return _dir_remover


@pytest.fixture
async def create_directory_with_files(
    create_empty_directory: Callable[..., Awaitable[FileUploadSchema]],
    populate_directory: Callable[..., Awaitable[None]],
    delete_directory: Callable[..., Awaitable[None]],
) -> Callable[..., AbstractAsyncContextManager[FileUploadSchema]]:
    @asynccontextmanager
    async def _create_context(
        dir_name: str, file_size_in_dir: ByteSize, subdir_count: int, file_count: int
    ) -> AsyncIterator[FileUploadSchema]:
        directory_file_upload: FileUploadSchema = await create_empty_directory(
            dir_name=dir_name
        )

        await populate_directory(
            file_size_in_dir=file_size_in_dir,
            dir_name=dir_name,
            subdir_count=subdir_count,
            file_count=file_count,
        )

        yield directory_file_upload

        await delete_directory(directory_file_upload=directory_file_upload)

    return _create_context

# pylint: disable=no-member
# pylint: disable=no-name-in-module
# pylint: disable=redefined-outer-name
# pylint: disable=unsupported-assignment-operation
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import datetime
import logging
import random
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from functools import partial
from pathlib import Path
from typing import Any, Final, cast

import httpx
import pytest
import respx
import simcore_service_storage
from asgi_lifespan import LifespanManager
from aws_library.s3 import SimcoreS3API
from celery import Celery
from celery.contrib.testing.worker import TestWorkController, start_worker
from celery.signals import worker_init, worker_shutdown
from celery.worker.worker import WorkController
from celery_library.signals import on_worker_init, on_worker_shutdown
from faker import Faker
from fakeredis.aioredis import FakeRedis
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadSchema,
    LinkType,
    UploadedPart,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID, StorageFileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import ByteSize, TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.fastapi import url_from_operation_id
from pytest_simcore.helpers.httpx_assert_checks import assert_status
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import delenvs_from_dict, setenvs_from_dict
from pytest_simcore.helpers.s3 import upload_file_to_presigned_link
from pytest_simcore.helpers.storage_utils import (
    FileIDDict,
    ProjectWithFilesParams,
    get_updated_project,
)
from pytest_simcore.helpers.storage_utils_file_meta_data import (
    assert_file_meta_data_in_db,
)
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp import status
from servicelib.fastapi.celery.app_server import FastAPIAppServer
from servicelib.rabbitmq._client_rpc import RabbitMQRPCClient
from servicelib.utils import limited_gather
from settings_library.rabbit import RabbitSettings
from simcore_postgres_database.models.tokens import tokens
from simcore_postgres_database.storage_models import file_meta_data, projects, users
from simcore_service_storage.api._worker_tasks.tasks import setup_worker_tasks
from simcore_service_storage.core.application import create_app
from simcore_service_storage.core.settings import ApplicationSettings
from simcore_service_storage.datcore_dsm import DatCoreDataManager
from simcore_service_storage.dsm import get_dsm_provider
from simcore_service_storage.models import FileMetaData, FileMetaDataAtDB, S3BucketName
from simcore_service_storage.modules.celery.tasks import TaskQueue
from simcore_service_storage.modules.s3 import get_s3_client
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from sqlalchemy import literal_column
from sqlalchemy.ext.asyncio import AsyncEngine
from tenacity.asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from types_aiobotocore_s3 import S3Client
from yarl import URL

pytest_plugins = [
    "pytest_simcore.asyncio_event_loops",
    "pytest_simcore.aws_s3_service",
    "pytest_simcore.aws_server",
    "pytest_simcore.cli_runner",
    "pytest_simcore.disk_usage_monitoring",
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.file_extra",
    "pytest_simcore.httpbin_service",
    "pytest_simcore.logging",
    "pytest_simcore.openapi_specs",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pytest_global_environs",
    "pytest_simcore.rabbit_service",
    "pytest_simcore.repository_paths",
    "pytest_simcore.simcore_storage_data_models",
    "pytest_simcore.simcore_storage_datcore_adapter",
    "pytest_simcore.simcore_storage_service",
    "pytest_simcore.tracing",
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


@pytest.fixture
async def cleanup_user_projects_file_metadata(sqlalchemy_async_engine: AsyncEngine):
    yield
    # cleanup
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(file_meta_data.delete())
        await conn.execute(projects.delete())
        await conn.execute(users.delete())


@pytest.fixture
def simcore_s3_dsm(initialized_app: FastAPI) -> SimcoreS3DataManager:
    return cast(
        SimcoreS3DataManager,
        get_dsm_provider(initialized_app).get(SimcoreS3DataManager.get_location_id()),
    )


@pytest.fixture
async def storage_s3_client(initialized_app: FastAPI) -> SimcoreS3API:
    return get_s3_client(initialized_app)


@pytest.fixture
async def storage_s3_bucket(app_settings: ApplicationSettings) -> str:
    assert app_settings.STORAGE_S3
    return app_settings.STORAGE_S3.S3_BUCKET_NAME


@pytest.fixture
async def mock_rabbit_setup(mocker: MockerFixture) -> MockerFixture:
    mocker.patch("simcore_service_storage.core.application.setup_rabbitmq")
    mocker.patch("simcore_service_storage.core.application.setup_rpc_api_routes")
    return mocker


@pytest.fixture
def app_environment(
    mock_env_devel_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    external_envfile_dict: EnvVarsDict,
) -> EnvVarsDict:
    if external_envfile_dict:
        delenvs_from_dict(monkeypatch, mock_env_devel_environment, raising=False)
        return setenvs_from_dict(monkeypatch, {**external_envfile_dict})

    envs = setenvs_from_dict(monkeypatch, {})
    return mock_env_devel_environment | envs


@pytest.fixture
def disabled_rabbitmq(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("STORAGE_RABBITMQ", "null")


@pytest.fixture
def enable_tracing(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    setup_tracing_fastapi: InMemorySpanExporter,
):
    monkeypatch.setenv("STORAGE_TRACING", "{}")


@pytest.fixture
def enabled_rabbitmq(
    app_environment: EnvVarsDict, rabbit_service: RabbitSettings
) -> RabbitSettings:
    return rabbit_service


@pytest.fixture
async def mocked_redis_server(mocker: MockerFixture) -> None:
    mock_redis = FakeRedis()
    mocker.patch("redis.asyncio.from_url", return_value=mock_redis)


@pytest.fixture
def app_settings(
    enable_tracing,
    app_environment: EnvVarsDict,
    enabled_rabbitmq: RabbitSettings,
    sqlalchemy_async_engine: AsyncEngine,
    postgres_host_config: dict[str, str],
    mocked_s3_server_envs: EnvVarsDict,
    datcore_adapter_service_mock: respx.MockRouter,
    mocked_redis_server: None,
) -> ApplicationSettings:
    test_app_settings = ApplicationSettings.create_from_envs()
    print(f"{test_app_settings.model_dump_json(indent=2)=}")
    return test_app_settings


_LIFESPAN_TIMEOUT: Final[int] = 10


@pytest.fixture
async def initialized_app(
    mock_celery_app: None,
    app_settings: ApplicationSettings,
) -> AsyncIterator[FastAPI]:
    app = create_app(app_settings)
    # NOTE: the timeout is sometime too small for CI machines, and even larger machines
    async with LifespanManager(
        app, startup_timeout=_LIFESPAN_TIMEOUT, shutdown_timeout=_LIFESPAN_TIMEOUT
    ):
        yield app


@pytest.fixture
async def client(
    initialized_app: FastAPI,
) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=initialized_app),
        base_url=f"http://{initialized_app.title}.testserver.io",
        headers={"Content-Type": "application/json"},
    ) as client:
        yield client


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
        DatCoreDataManager.get_location_id(),
    ],
    ids=[
        SimcoreS3DataManager.get_location_name(),
        DatCoreDataManager.get_location_name(),
    ],
)
def location_id(request: pytest.FixtureRequest) -> LocationID:
    return request.param  # type: ignore


@pytest.fixture
async def get_file_meta_data(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
) -> Callable[..., Awaitable[FileMetaDataGet]]:
    async def _getter(file_id: SimcoreS3FileID) -> FileMetaDataGet:
        url = url_from_operation_id(
            client,
            initialized_app,
            "get_file_metadata",
            location_id=f"{location_id}",
            file_id=file_id,
        ).with_query(user_id=user_id)

        response = await client.get(f"{url}")
        received_fmd, error = assert_status(
            response, status.HTTP_200_OK, FileMetaDataGet
        )
        assert not error
        assert received_fmd
        return received_fmd

    return _getter


@pytest.fixture
async def create_upload_file_link_v2(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
) -> AsyncIterator[Callable[..., Awaitable[FileUploadSchema]]]:
    file_params: list[tuple[UserID, int, SimcoreS3FileID]] = []

    async def _link_creator(
        file_id: SimcoreS3FileID, **query_kwargs
    ) -> FileUploadSchema:
        url = url_from_operation_id(
            client,
            initialized_app,
            "upload_file",
            location_id=f"{location_id}",
            file_id=file_id,
        ).with_query(**query_kwargs, user_id=user_id)
        assert (
            "file_size" in url.query
        ), "V2 call to upload file must contain file_size field!"
        response = await client.put(f"{url}")
        received_file_upload, error = assert_status(
            response, status.HTTP_200_OK, FileUploadSchema
        )
        assert not error
        assert received_file_upload
        file_params.append((user_id, location_id, file_id))
        return received_file_upload

    yield _link_creator

    # cleanup
    clean_tasks = []
    for u_id, loc_id, file_id in file_params:
        url = url_from_operation_id(
            client,
            initialized_app,
            "delete_file",
            location_id=f"{loc_id}",
            file_id=file_id,
        ).with_query(user_id=u_id)
        clean_tasks.append(client.delete(f"{url}"))
    await asyncio.gather(*clean_tasks)


@pytest.fixture
def upload_file(
    sqlalchemy_async_engine: AsyncEngine,
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    client: httpx.AsyncClient,
    project_id: ProjectID,
    node_id: NodeID,
    create_upload_file_link_v2: Callable[..., Awaitable[FileUploadSchema]],
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    create_simcore_file_id: Callable[[ProjectID, NodeID, str], SimcoreS3FileID],
    with_storage_celery_worker: TestWorkController,
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
        # create a file
        file = create_file_of_size(file_size, file_name)
        if not file_id:
            file_id = create_simcore_file_id(project_id, node_id, file_name)
        # get an upload link
        query_params: dict = {}
        if sha256_checksum:
            query_params["sha256_checksum"] = f"{sha256_checksum}"
        file_upload_link = await create_upload_file_link_v2(
            file_id,
            link_type=LinkType.PRESIGNED.value,
            file_size=file_size,
            **query_params,
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
            file_upload_complete_response, error = assert_status(
                response, status.HTTP_202_ACCEPTED, FileUploadCompleteResponse
            )
            assert not error
            assert file_upload_complete_response
            state_url = URL(f"{file_upload_complete_response.links.state}").relative()

            completion_etag = None
            async for attempt in AsyncRetrying(
                reraise=True,
                wait=wait_fixed(1),
                stop=stop_after_delay(60),
                retry=retry_if_exception_type(ValueError),
            ):
                with (
                    attempt,
                    log_context(
                        logging.INFO,
                        f"waiting for upload completion {state_url=}, {attempt.retry_state.attempt_number}",
                    ) as ctx,
                ):
                    response = await client.post(f"{state_url}")
                    response.raise_for_status()
                    future, error = assert_status(
                        response, status.HTTP_200_OK, FileUploadCompleteFutureResponse
                    )
                    assert not error
                    assert future
                    if future.state == FileUploadCompleteState.NOK:
                        msg = f"{future=}"
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
            sqlalchemy_async_engine,
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
    client: httpx.AsyncClient,
    with_storage_celery_worker: TestWorkController,
) -> Callable[[str, ProjectID, NodeID], Awaitable[SimcoreS3FileID]]:
    async def _directory_creator(
        dir_name: str, project_id: ProjectID, node_id: NodeID
    ) -> SimcoreS3FileID:
        # creating an empty directory goes through the same procedure as uploading a multipart file
        # done by using 3 calls:
        # 1. create the link as a directory
        # 2. call complete_upload link
        # 3. call file_upload_complete_response until it replies OK

        directory_file_id = create_simcore_file_id(project_id, node_id, dir_name)
        directory_file_upload = await create_upload_file_link_v2(
            directory_file_id, link_type="S3", is_directory="true", file_size=0
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
        file_upload_complete_response, error = assert_status(
            response, status.HTTP_202_ACCEPTED, FileUploadCompleteResponse
        )
        assert not error
        assert file_upload_complete_response
        state_url = URL(f"{file_upload_complete_response.links.state}").relative()

        # now check for the completion
        async for attempt in AsyncRetrying(
            reraise=True,
            wait=wait_fixed(1),
            stop=stop_after_delay(60),
            retry=retry_if_exception_type(AssertionError),
        ):
            with (
                attempt,
                log_context(
                    logging.INFO,
                    f"waiting for upload completion {state_url=}, {attempt.retry_state.attempt_number}",
                ) as ctx,
            ):
                response = await client.post(f"{state_url}")
                future, error = assert_status(
                    response, status.HTTP_200_OK, FileUploadCompleteFutureResponse
                )
                assert not error
                assert future
                assert future.state == FileUploadCompleteState.OK
                assert future.e_tag is None
                ctx.logger.info(
                    "%s",
                    f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]",
                )

        return directory_file_id

    return _directory_creator


async def _upload_file_to_s3(
    s3_client: SimcoreS3API,
    faker: Faker,
    *,
    s3_bucket: S3BucketName,
    local_file: Path,
    file_id: SimcoreS3FileID,
) -> dict[SHA256Str, FileIDDict]:
    await s3_client.upload_file(
        bucket=s3_bucket,
        file=local_file,
        object_key=file_id,
        bytes_transfered_cb=None,
    )
    return {file_id: FileIDDict(path=local_file, sha256_checksum=f"{faker.sha256()}")}


@pytest.fixture
async def populate_directory(
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    storage_s3_client: SimcoreS3API,
    storage_s3_bucket: S3BucketName,
    faker: Faker,
) -> Callable[
    [ByteSize, str, ProjectID, NodeID, int, int],
    Awaitable[tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]],
]:
    async def _create_content(
        file_size_in_dir: ByteSize,
        dir_name: str,
        project_id: ProjectID,
        node_id: NodeID,
        subdir_count: int,
        file_count: int,
    ) -> tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]:
        assert subdir_count >= 1, "cannot use fixture with subdir_count < 1!"
        assert file_count >= 1, "cannot use fixture with file_count < 1!"

        local_file = create_file_of_size(file_size_in_dir, None)

        # Create subdirectories
        s3_base_path = Path(f"{project_id}") / f"{node_id}" / dir_name
        # NOTE: add a space in the sub directory
        s3_subdirs = [
            s3_base_path / f"sub-dir_ect ory-{i}" for i in range(subdir_count)
        ]
        # Randomly distribute files across subdirectories
        selected_subdirs = random.choices(s3_subdirs, k=file_count)  # noqa: S311
        # Upload to S3
        with log_context(
            logging.INFO,
            msg=f"Uploading {file_count} files to S3 (each {file_size_in_dir.human_readable()}, total: {ByteSize(file_count * file_size_in_dir).human_readable()})",
        ):
            # we ensure the file name contain a space
            def _file_name_with_space():
                file_name = faker.unique.file_name()
                return f"{file_name[:1]} {file_name[1:]}"

            results = await asyncio.gather(
                *(
                    _upload_file_to_s3(
                        storage_s3_client,
                        faker,
                        s3_bucket=storage_s3_bucket,
                        local_file=local_file,
                        file_id=TypeAdapter(SimcoreS3FileID).validate_python(
                            f"{selected_subdir / _file_name_with_space()}"
                        ),
                    )
                    for selected_subdir in selected_subdirs
                )
            )

        assert len(results) == file_count

        # check this is true
        counted_uploaded_objects = await storage_s3_client.count_objects(
            bucket=storage_s3_bucket,
            prefix=s3_base_path,
            is_partial_prefix=True,
            start_after=None,
            use_delimiter=False,
        )
        assert counted_uploaded_objects == file_count

        return node_id, {k: v for r in results for k, v in r.items()}

    return _create_content


@pytest.fixture
async def delete_directory(
    initialized_app: FastAPI,
    client: httpx.AsyncClient,
    user_id: UserID,
    location_id: LocationID,
) -> Callable[[StorageFileID], Awaitable[None]]:
    async def _dir_remover(directory_s3: StorageFileID) -> None:
        delete_url = url_from_operation_id(
            client,
            initialized_app,
            "delete_file",
            location_id=f"{location_id}",
            file_id=directory_s3,
        ).with_query(user_id=user_id)

        response = await client.delete(f"{delete_url}")
        assert_status(response, status.HTTP_204_NO_CONTENT, None)

        # NOTE: ensures no more files are left in the directory,
        # even if one file is left this will detect it
        list_files_metadata_url = url_from_operation_id(
            client, initialized_app, "list_files_metadata", location_id=f"{location_id}"
        ).with_query(user_id=user_id, uuid_filter=directory_s3)
        response = await client.get(f"{list_files_metadata_url}")
        data, error = assert_status(response, status.HTTP_200_OK, list[FileMetaDataGet])
        assert error is None
        assert data == []

    return _dir_remover


@pytest.fixture
async def create_directory_with_files(
    create_empty_directory: Callable[
        [str, ProjectID, NodeID], Awaitable[SimcoreS3FileID]
    ],
    populate_directory: Callable[
        [ByteSize, str, ProjectID, NodeID, int, int],
        Awaitable[tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]],
    ],
    delete_directory: Callable[..., Awaitable[None]],
) -> AsyncIterator[
    Callable[
        [str, ByteSize, int, int, ProjectID, NodeID],
        Awaitable[
            tuple[SimcoreS3FileID, tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ]
]:
    uploaded_directories = []

    async def _(
        dir_name: str,
        file_size_in_dir: ByteSize,
        subdir_count: int,
        file_count: int,
        project_id: ProjectID,
        node_id: NodeID,
    ) -> tuple[SimcoreS3FileID, tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]]:
        directory_file_id = await create_empty_directory(dir_name, project_id, node_id)

        uploaded_files = await populate_directory(
            file_size_in_dir,
            dir_name,
            project_id,
            node_id,
            subdir_count,
            file_count,
        )

        uploaded_directories.append(directory_file_id)

        return directory_file_id, uploaded_files

    yield _

    await asyncio.gather(*(delete_directory(_) for _ in uploaded_directories))


async def _upload_one_file_task(
    upload_file: Callable[..., Awaitable[tuple[Path, SimcoreS3FileID]]],
    allowed_file_sizes: tuple[ByteSize, ...],
    allowed_file_checksums: tuple[SHA256Str, ...],
    *,
    file_name: str,
    file_id: SimcoreS3FileID,
    node_id: NodeID,
) -> tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]:
    selected_checksum = random.choice(allowed_file_checksums)  # noqa: S311
    uploaded_file, uploaded_file_id = await upload_file(
        file_size=random.choice(allowed_file_sizes),  # noqa: S311
        file_name=file_name,
        file_id=file_id,
        sha256_checksum=selected_checksum,
    )
    assert uploaded_file_id == file_id
    return (
        node_id,
        {
            uploaded_file_id: FileIDDict(
                path=uploaded_file, sha256_checksum=selected_checksum
            )
        },
    )


async def _upload_folder_task(
    create_directory_with_files: Callable[
        ...,
        Awaitable[
            tuple[SimcoreS3FileID, tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    allowed_file_sizes: tuple[ByteSize, ...],
    *,
    dir_name: str,
    project_id: ProjectID,
    node_id: NodeID,
    workspace_file_count: int,
) -> tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]:
    dir_file_id, node_files_map = await create_directory_with_files(
        dir_name=dir_name,
        file_size_in_dir=random.choice(allowed_file_sizes),  # noqa: S311
        subdir_count=3,
        file_count=workspace_file_count,
        project_id=project_id,
        node_id=node_id,
    )
    assert dir_file_id
    return node_files_map


@pytest.fixture
async def random_project_with_files(
    sqlalchemy_async_engine: AsyncEngine,
    create_project: Callable[..., Awaitable[dict[str, Any]]],
    create_project_node: Callable[..., Awaitable[NodeID]],
    create_simcore_file_id: Callable[
        [ProjectID, NodeID, str, Path | None], SimcoreS3FileID
    ],
    faker: Faker,
    create_directory_with_files: Callable[
        ...,
        Awaitable[
            tuple[SimcoreS3FileID, tuple[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    upload_file: Callable[..., Awaitable[tuple[Path, SimcoreS3FileID]]],
) -> Callable[
    [ProjectWithFilesParams],
    Awaitable[tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]],
]:
    async def _creator(
        project_params: ProjectWithFilesParams,
    ) -> tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]:
        assert len(project_params.allowed_file_sizes) == len(
            project_params.allowed_file_checksums
        )
        project = await create_project(name="random-project")
        node_to_files_mapping: dict[NodeID, dict[SimcoreS3FileID, FileIDDict]] = {}
        upload_tasks = []
        for _ in range(project_params.num_nodes):
            # Create a node with outputs (files and others)
            project_id = ProjectID(project["uuid"])
            node_id = cast(NodeID, faker.uuid4(cast_to=None))
            node_to_files_mapping[node_id] = {}
            output3_file_name = faker.file_name()
            output3_file_id = create_simcore_file_id(
                project_id, node_id, output3_file_name, Path("outputs/output_3")
            )
            created_node_id = await create_project_node(
                ProjectID(project["uuid"]),
                node_id,
                outputs={
                    "output_1": faker.pyint(),
                    "output_2": faker.pystr(),
                    "output_3": f"{output3_file_id}",
                },
            )
            assert created_node_id == node_id

            upload_tasks.append(
                _upload_one_file_task(
                    upload_file,
                    project_params.allowed_file_sizes,
                    project_params.allowed_file_checksums,
                    file_name=output3_file_name,
                    file_id=output3_file_id,
                    node_id=node_id,
                )
            )

            # some workspace files (these are not referenced in the file_meta_data, only as a folder)
            if project_params.workspace_files_count > 0:
                upload_tasks.append(
                    _upload_folder_task(
                        create_directory_with_files,
                        project_params.allowed_file_sizes,
                        dir_name="workspace",
                        project_id=project_id,
                        node_id=node_id,
                        workspace_file_count=project_params.workspace_files_count,
                    )
                )

            # add a few random files in the node root space for good measure
            for _ in range(random.randint(1, 3)):  # noqa: S311
                root_file_name = faker.file_name()
                root_file_id = create_simcore_file_id(
                    project_id, node_id, root_file_name, None
                )
                upload_tasks.append(
                    _upload_one_file_task(
                        upload_file,
                        project_params.allowed_file_sizes,
                        project_params.allowed_file_checksums,
                        file_name=root_file_name,
                        file_id=root_file_id,
                        node_id=node_id,
                    ),
                )

        # upload everything of the node
        results = await limited_gather(*upload_tasks, limit=10)

        for node_id, file_id_to_dict_mapping in results:
            for file_id, file_dict in file_id_to_dict_mapping.items():
                node_to_files_mapping[node_id][file_id] = file_dict

        project = await get_updated_project(sqlalchemy_async_engine, project["uuid"])
        return project, node_to_files_mapping

    return _creator


@pytest.fixture
async def with_random_project_with_files(
    random_project_with_files: Callable[
        [ProjectWithFilesParams],
        Awaitable[
            tuple[dict[str, Any], dict[NodeID, dict[SimcoreS3FileID, FileIDDict]]]
        ],
    ],
    project_params: ProjectWithFilesParams,
) -> tuple[
    dict[str, Any],
    dict[NodeID, dict[SimcoreS3FileID, FileIDDict]],
]:
    return await random_project_with_files(project_params)


@pytest.fixture()
async def output_file(
    user_id: UserID, project_id: str, sqlalchemy_async_engine: AsyncEngine, faker: Faker
) -> AsyncIterator[FileMetaData]:
    node_id = "fd6f9737-1988-341b-b4ac-0614b646fa82"

    # pylint: disable=no-value-for-parameter

    file = FileMetaData.from_simcore_node(
        user_id=user_id,
        file_id=f"{project_id}/{node_id}/filename.txt",
        bucket=TypeAdapter(S3BucketName).validate_python("master-simcore"),
        location_id=SimcoreS3DataManager.get_location_id(),
        location_name=SimcoreS3DataManager.get_location_name(),
        sha256_checksum=TypeAdapter(SHA256Str).validate_python(
            faker.sha256(raw_output=False)
        ),
    )
    file.entity_tag = "df9d868b94e53d18009066ca5cd90e9f"
    file.file_size = ByteSize(12)
    file.user_id = user_id
    async with sqlalchemy_async_engine.begin() as conn:
        stmt = (
            file_meta_data.insert()
            .values(jsonable_encoder(FileMetaDataAtDB.model_validate(file)))
            .returning(literal_column("*"))
        )
        result = await conn.execute(stmt)
        row = result.one()
        assert row

    yield file

    async with sqlalchemy_async_engine.begin() as conn:
        result = await conn.execute(
            file_meta_data.delete().where(file_meta_data.c.file_id == row.file_id)
        )


@pytest.fixture
async def fake_datcore_tokens(
    user_id: UserID, sqlalchemy_async_engine: AsyncEngine, faker: Faker
) -> AsyncIterator[tuple[str, str]]:
    token_key = cast(str, faker.uuid4())
    token_secret = cast(str, faker.uuid4())
    created_token_ids = []
    async with sqlalchemy_async_engine.begin() as conn:
        result = await conn.execute(
            tokens.insert()
            .values(
                user_id=user_id,
                token_service="pytest",  # noqa: S106
                token_data={
                    "service": "pytest",
                    "token_secret": token_secret,
                    "token_key": token_key,
                },
            )
            .returning(tokens.c.token_id)
        )
        row = result.one()
        created_token_ids.append(row.token_id)
    yield token_key, token_secret

    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            tokens.delete().where(tokens.c.token_id.in_(created_token_ids))
        )


@pytest.fixture(scope="session")
def celery_config() -> dict[str, Any]:
    return {
        "broker_connection_retry_on_startup": True,
        "broker_url": "memory://localhost//",
        "result_backend": "cache+memory://localhost//",
        "result_expires": datetime.timedelta(days=7),
        "result_extended": True,
        "pool": "threads",
        "task_default_queue": "default",
        "task_send_sent_event": True,
        "task_track_started": True,
        "worker_send_task_events": True,
    }


@pytest.fixture
def mock_celery_app(mocker: MockerFixture, celery_config: dict[str, Any]) -> Celery:
    celery_app = Celery(**celery_config)

    for module in ("simcore_service_storage.modules.celery.create_app",):
        mocker.patch(module, return_value=celery_app)

    return celery_app


@pytest.fixture
def register_celery_tasks() -> Callable[[Celery], None]:
    """override if tasks are needed"""

    def _(celery_app: Celery) -> None: ...

    return _


@pytest.fixture
async def with_storage_celery_worker(
    app_environment: EnvVarsDict,
    celery_app: Celery,
    monkeypatch: pytest.MonkeyPatch,
    register_celery_tasks: Callable[[Celery], None],
) -> AsyncIterator[TestWorkController]:
    # Signals must be explicitily connected
    monkeypatch.setenv("STORAGE_WORKER_MODE", "true")
    app_settings = ApplicationSettings.create_from_envs()

    app_server = FastAPIAppServer(app=create_app(app_settings))

    def _on_worker_init_wrapper(sender: WorkController, **_kwargs):
        assert app_settings.STORAGE_CELERY  # nosec
        return partial(on_worker_init, app_server, app_settings.STORAGE_CELERY)(
            sender, **_kwargs
        )

    worker_init.connect(_on_worker_init_wrapper)
    worker_shutdown.connect(on_worker_shutdown)

    setup_worker_tasks(celery_app)
    register_celery_tasks(celery_app)

    with start_worker(
        celery_app,
        pool="threads",
        concurrency=1,
        loglevel="info",
        perform_ping_check=False,
        queues=",".join(queue.value for queue in TaskQueue),
    ) as worker:
        yield worker


@pytest.fixture
async def storage_rabbitmq_rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    rpc_client = await rabbitmq_rpc_client("pytest_storage_rpc_client")
    assert rpc_client
    return rpc_client


@pytest.fixture
def product_name(faker: Faker) -> str:
    return faker.name()


@pytest.fixture
def set_log_levels_for_noisy_libraries() -> None:
    # Reduce the log level for 'werkzeug'
    logging.getLogger("werkzeug").setLevel(logging.WARNING)

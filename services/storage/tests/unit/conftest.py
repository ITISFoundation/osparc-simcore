# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
import urllib.parse
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncContextManager

import openapi_core
import pytest
import yaml
from aiohttp import web
from aiohttp.test_utils import TestClient
from models_library.api_schemas_storage import (
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadCompletionBody,
    FileUploadSchema,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, NodeID, SimcoreS3FileID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_storage._meta import api_vtag
from simcore_service_storage.handlers_files import UPLOAD_TASKS_KEY
from simcore_service_storage.models import S3BucketName
from simcore_service_storage.resources import storage_resources
from simcore_service_storage.s3_client import StorageS3Client
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed
from yarl import URL


@pytest.fixture(scope="module")
def openapi_specs():
    spec_path: Path = storage_resources.get_path(f"api/{api_vtag}/openapi.yaml")
    spec_dict: dict[str, Any] = yaml.safe_load(spec_path.read_text())
    api_specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())
    return api_specs


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
        complete_url = URL(directory_file_upload.links.complete_upload).relative()
        response = await client.post(
            f"{complete_url}",
            json=jsonable_encoder(FileUploadCompletionBody(parts=[])),
        )
        response.raise_for_status()
        data, error = await assert_status(response, web.HTTPAccepted)
        assert not error
        assert data
        file_upload_complete_response = FileUploadCompleteResponse.parse_obj(data)
        state_url = URL(file_upload_complete_response.links.state).relative()

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
            with attempt:
                print(
                    f"--> checking for upload {state_url=}, {attempt.retry_state.attempt_number}..."
                )
                response = await client.post(f"{state_url}")
                data, error = await assert_status(response, web.HTTPOk)
                assert not error
                assert data
                future = FileUploadCompleteFutureResponse.parse_obj(data)
                assert future.state == FileUploadCompleteState.OK
                assert future.e_tag is None
                print(
                    f"--> done waiting, data is completely uploaded [{attempt.retry_state.retry_object.statistics}]"
                )

        return directory_file_upload

    return _directory_creator


@pytest.fixture
async def populate_directory(
    create_file_of_size: Callable[[ByteSize, str | None], Path],
    storage_s3_client: StorageS3Client,
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
                storage_s3_bucket, file, SimcoreS3FileID(f"{clean_path}"), None
            )

        tasks: deque = deque()
        for s in range(subdir_count):
            for f in range(file_count):
                tasks.append(_create_file(s, f))

        await asyncio.gather(*tasks)

        file.unlink()

    return _create_content


@pytest.fixture
async def delete_directory(
    client: TestClient,
    storage_s3_client: StorageS3Client,
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
        await assert_status(response, web.HTTPNoContent)

        # NOTE: ensures no more files are left in the directory,
        # even if one file is left this will detect it
        files = await storage_s3_client.list_files(
            bucket=storage_s3_bucket, prefix=directory_file_id
        )
        assert len(files) == 0

    return _dir_remover


@pytest.fixture
async def directory_with_files(
    create_empty_directory: Callable[..., Awaitable[FileUploadSchema]],
    populate_directory: Callable[..., Awaitable[None]],
    delete_directory: Callable[..., Awaitable[None]],
) -> Callable[..., AsyncContextManager[FileUploadSchema]]:
    @asynccontextmanager
    async def _context_manager(
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

    return _context_manager

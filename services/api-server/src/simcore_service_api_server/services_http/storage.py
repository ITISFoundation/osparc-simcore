import logging
import re
import urllib.parse
from datetime import timedelta
from functools import partial
from mimetypes import guess_type
from typing import Final, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_storage.storage_schemas import (
    ETag,
    FileMetaDataArray,
)
from models_library.api_schemas_storage.storage_schemas import (
    FileMetaDataGet as StorageFileMetaData,
)
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompleteState,
    FileUploadSchema,
    LinkType,
    PresignedLink,
)
from models_library.basic_types import SHA256Str
from models_library.generics import Envelope
from models_library.rest_pagination import PageLimitInt, PageOffsetInt
from pydantic import AnyUrl
from settings_library.tracing import TracingSettings
from simcore_service_api_server.models.schemas.files import UserFile
from simcore_service_api_server.models.schemas.jobs import UserFileToProgramJob
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_delay,
    wait_fixed,
)

from ..core.settings import StorageSettings
from ..exceptions.service_errors_utils import service_exception_mapper
from ..models.domain.files import File
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_POLL_TIMEOUT: Final[timedelta] = timedelta(minutes=10)


_logger = logging.getLogger(__name__)

_exception_mapper = partial(service_exception_mapper, service_name="Storage")

AccessRight = Literal["read", "write"]

_FILE_ID_PATTERN = re.compile(r"^api\/(?P<file_id>[\w-]+)\/(?P<filename>.+)$")


def to_file_api_model(stored_file_meta: StorageFileMetaData) -> File:
    # extracts fields from api/{file_id}/{filename}
    match = _FILE_ID_PATTERN.match(stored_file_meta.file_id or "")
    if not match:
        msg = f"Invalid file_id {stored_file_meta.file_id} in file metadata"
        raise ValueError(msg)

    file_id, filename = match.groups()

    return File(
        id=file_id,  # type: ignore
        filename=filename,
        content_type=guess_type(stored_file_meta.file_name)[0]
        or "application/octet-stream",
        e_tag=stored_file_meta.entity_tag,
        checksum=stored_file_meta.sha256_checksum,
    )


class StorageApi(BaseServiceClientApi):
    #
    # All files created via the API are stored in simcore-s3 as objects with name pattern "api/{file_id}/{filename.ext}"
    #
    SIMCORE_S3_ID = 0

    @_exception_mapper(http_status_map={})
    async def list_files(
        self,
        *,
        user_id: int,
    ) -> list[StorageFileMetaData]:
        """Lists metadata of all s3 objects name as api/* from a given user"""

        # search_files_starting_with
        response = await self.client.post(
            "/simcore-s3/files/metadata:search",
            params={
                "kind": "owned",
                "user_id": str(user_id),
                "startswith": "api/",
            },
        )
        response.raise_for_status()

        files_metadata = (
            Envelope[FileMetaDataArray].model_validate_json(response.text).data
        )
        files: list[StorageFileMetaData] = (
            [] if files_metadata is None else files_metadata.root
        )
        return files

    @_exception_mapper(http_status_map={})
    async def search_owned_files(
        self,
        *,
        user_id: int,
        file_id: UUID | None,
        sha256_checksum: SHA256Str | None = None,
        limit: PageLimitInt | None = None,
        offset: PageOffsetInt | None = None,
    ) -> list[StorageFileMetaData]:
        # NOTE: can NOT use /locations/0/files/metadata with uuid_filter=api/ because
        # logic in storage 'wrongly' assumes that all data is associated to a project and
        # here there is no project, so it would always returns an empty
        response = await self.client.post(
            "/simcore-s3/files/metadata:search",
            params=jsonable_encoder(
                {
                    "kind": "owned",
                    "user_id": f"{user_id}",
                    "startswith": "api/" if file_id is None else f"api/{file_id}",
                    "sha256_checksum": sha256_checksum,
                    "limit": limit,
                    "offset": offset,
                },
                exclude_none=True,
            ),
        )
        response.raise_for_status()

        files_metadata = (
            Envelope[FileMetaDataArray].model_validate_json(response.text).data
        )
        files: list[StorageFileMetaData] = (
            [] if files_metadata is None else files_metadata.root
        )
        assert len(files) <= limit if limit else True  # nosec
        return files

    @_exception_mapper(http_status_map={})
    async def get_download_link(
        self, *, user_id: int, file_id: UUID, file_name: str
    ) -> AnyUrl:
        object_path = urllib.parse.quote_plus(f"api/{file_id}/{file_name}")

        response = await self.client.get(
            f"/locations/{self.SIMCORE_S3_ID}/files/{object_path}",
            params={"user_id": str(user_id)},
        )
        response.raise_for_status()

        presigned_link: PresignedLink | None = (
            Envelope[PresignedLink].model_validate_json(response.text).data
        )
        assert presigned_link is not None
        link: AnyUrl = presigned_link.link
        return link

    @_exception_mapper(http_status_map={})
    async def delete_file(self, *, user_id: int, quoted_storage_file_id: str) -> None:
        response = await self.client.delete(
            f"/locations/{self.SIMCORE_S3_ID}/files/{quoted_storage_file_id}",
            params={"user_id": user_id},
        )
        response.raise_for_status()

    @_exception_mapper(http_status_map={})
    async def get_file_upload_links(
        self, *, user_id: int, file: File, client_file: UserFileToProgramJob | UserFile
    ) -> FileUploadSchema:

        query_params = {
            "user_id": f"{user_id}",
            "link_type": LinkType.PRESIGNED.value,
            "file_size": int(client_file.filesize),
            "is_directory": "false",
            "sha256_checksum": f"{client_file.sha256_checksum}",
        }

        # complete_upload_file
        response = await self.client.put(
            f"/locations/{self.SIMCORE_S3_ID}/files/{file.quoted_storage_file_id}:upload",
            params=query_params,
        )
        response.raise_for_status()

        enveloped_data = Envelope[FileUploadSchema].model_validate_json(response.text)
        assert enveloped_data.data  # nosec
        return enveloped_data.data

    @_exception_mapper(http_status_map={})
    async def complete_file_upload(self, *, user_id: int, file: File) -> ETag:

        response = await self.client.post(
            f"/locations/{self.SIMCORE_S3_ID}/files/{file.quoted_storage_file_id}:complete",
            params={"user_id": f"{user_id}"},
        )
        response.raise_for_status()
        file_upload_complete_response = Envelope[
            FileUploadCompleteResponse
        ].model_validate_json(response.text)
        assert file_upload_complete_response.data  # nosec
        state_url = f"{file_upload_complete_response.data.links.state}"
        async for attempt in AsyncRetrying(
            reraise=False,
            wait=wait_fixed(1),
            stop=stop_after_delay(_POLL_TIMEOUT),
            retry=retry_if_exception_type(ValueError),
            before_sleep=before_sleep_log(_logger, logging.DEBUG),
        ):
            with attempt:
                resp = await self.client.post(state_url)
                resp.raise_for_status()
                future_enveloped = Envelope[
                    FileUploadCompleteFutureResponse
                ].model_validate_json(resp.text)
                assert future_enveloped.data  # nosec
                if future_enveloped.data.state == FileUploadCompleteState.NOK:
                    msg = "upload not ready yet"
                    raise ValueError(msg)

                assert future_enveloped.data.e_tag  # nosec
                _logger.debug(
                    "multipart upload completed in %s, received %s",
                    attempt.retry_state.retry_object.statistics,
                    f"{future_enveloped.data.e_tag=}",
                )
                return future_enveloped.data.e_tag
        msg = f"Could not complete the upload for file '{file.filename}' (id: {file.id}) within the allocated time."
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=msg,
        )

    @_exception_mapper(http_status_map={})
    async def abort_file_upload(self, *, user_id: int, file: File) -> None:
        response = await self.client.post(
            f"/locations/{self.SIMCORE_S3_ID}/files/{file.quoted_storage_file_id}:abort",
            params={"user_id": f"{user_id}"},
        )
        response.raise_for_status()

    @_exception_mapper(http_status_map={})
    async def create_soft_link(
        self, *, user_id: int, target_s3_path: str, as_file_id: UUID
    ) -> File:
        assert len(target_s3_path.split("/")) == 3  # nosec

        # define api-prefixed object-path for link
        file_id: str = f"{as_file_id}"
        file_name = target_s3_path.split("/")[-1]
        link_path = f"api/{file_id}/{file_name}"

        file_id = urllib.parse.quote_plus(target_s3_path)

        # ln makes links between files
        # ln TARGET LINK_NAME
        response = await self.client.post(
            f"/files/{file_id}:soft-copy",
            params={"user_id": user_id},
            json={"link_id": link_path},
        )
        response.raise_for_status()

        stored_file_meta = (
            Envelope[StorageFileMetaData].model_validate_json(response.text).data
        )
        assert stored_file_meta is not None
        file_meta: File = to_file_api_model(stored_file_meta)
        return file_meta


# MODULES APP SETUP -------------------------------------------------------------


def setup(
    app: FastAPI, settings: StorageSettings, tracing_settings: TracingSettings | None
) -> None:
    if not settings:
        settings = StorageSettings()

    setup_client_instance(
        app,
        StorageApi,
        api_baseurl=settings.api_base_url,
        service_name="storage",
        tracing_settings=tracing_settings,
    )


__all__: tuple[str, ...] = (
    "StorageApi",
    "StorageFileMetaData",
    "setup",
    "to_file_api_model",
)

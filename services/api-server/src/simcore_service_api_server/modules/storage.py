import logging
import re
import urllib.parse
from mimetypes import guess_type
from typing import List
from uuid import UUID

import httpx
from fastapi import FastAPI
from models_library.api_schemas_storage import FileMetaData as StorageFileMetaData
from models_library.api_schemas_storage import FileMetaDataArray, PresignedLink

from ..core.settings import StorageSettings
from ..models.schemas.files import File
from ..utils.client_base import BaseServiceClientApi

## from ..utils.client_decorators import JsonDataType, handle_errors, handle_retry

logger = logging.getLogger(__name__)

# Module's setup logic ---------------------------------------------


def setup(app: FastAPI, settings: StorageSettings) -> None:
    if not settings:
        settings = StorageSettings()

    def on_startup() -> None:
        logger.debug("Setup %s at %s...", __name__, settings.base_url)
        StorageApi.create(
            app,
            client=httpx.AsyncClient(base_url=settings.base_url),
            service_name="storage",
        )

    async def on_shutdown() -> None:
        client = StorageApi.get_instance(app)
        if client:
            await client.aclose()
        logger.debug("%s client closed successfully", __name__)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


# API CLASS ---------------------------------------------


class StorageApi(BaseServiceClientApi):
    #
    # All files created via the API are stored in simcore-s3 as objects with name pattern "api/{file_id}/{filename.ext}"
    #
    SIMCORE_S3_ID = 0

    # FIXME: error handling and retrying policies?
    # @handle_errors("storage", logger, return_json=True)
    # @handle_retry(logger)
    # async def get(self, path: str, *args, **kwargs) -> JsonDataType:
    #     return await self.client.get(path, *args, **kwargs)

    async def list_files(self, user_id: int) -> List[StorageFileMetaData]:
        """ Lists metadata of all s3 objects name as api/* from a given user"""
        resp = await self.client.post(
            "/simcore-s3/files/metadata:search",
            params={
                "user_id": str(user_id),
                "startswith": "api/",
            },
        )
        # FIXME: handle HTTPStatusError
        resp.raise_for_status()

        files_metadata = FileMetaDataArray(__root__=resp.json()["data"] or [])
        return files_metadata.__root__

    async def search_files(
        self, user_id: int, file_id: UUID
    ) -> List[StorageFileMetaData]:
        # NOTE: can NOT use /locations/0/files/metadata with uuid_filter=api/ because
        # logic in storage 'wrongly' assumes that all data is associated to a project and
        # here there is no project, so it would always returns an empty
        resp = await self.client.post(
            "/simcore-s3/files/metadata:search",
            params={
                "user_id": str(user_id),
                "startswith": f"api/{file_id}",
            },
        )
        files_metadata = FileMetaDataArray(__root__=resp.json()["data"] or [])
        return files_metadata.__root__

    async def get_download_link(
        self, user_id: int, file_id: UUID, file_name: str
    ) -> str:
        object_path = urllib.parse.quote_plus(f"api/{file_id}/{file_name}")

        resp = await self.client.get(
            f"/locations/{self.SIMCORE_S3_ID}/files/{object_path}",
            params={"user_id": str(user_id)},
        )

        presigned_link = PresignedLink.parse_obj(resp.json()["data"])
        return presigned_link.link

    async def get_upload_link(self, user_id: int, file_id: UUID, file_name: str) -> str:
        object_path = urllib.parse.quote_plus(f"api/{file_id}/{file_name}")

        resp = await self.client.put(
            f"/locations/{self.SIMCORE_S3_ID}/files/{object_path}",
            params={
                "user_id": str(user_id),
            },
        )

        presigned_link = PresignedLink.parse_obj(resp.json()["data"])
        return presigned_link.link


FILE_ID_PATTERN = re.compile(r"^api\/(?P<file_id>[\w-]+)\/(?P<filename>.+)$")


def to_file_api_model(stored_file_meta: StorageFileMetaData) -> File:
    # extracts fields from api/{file_id}/{filename}
    match = FILE_ID_PATTERN.match(stored_file_meta.file_id or "")
    if not match:
        raise ValueError(f"Invalid file_id {stored_file_meta.file_id} in file metadata")

    file_id, filename = match.groups()

    meta = File(
        id=file_id,
        name=filename,
        # FIXME: UploadFile gets content from the request header while here is
        # mimetypes.guess_type used. Sometimes it does not match.
        # Add column in meta_data table of storage and stop guessing :-)
        content_type=guess_type(filename)[0] or "application/octet-stream",
        checksum=stored_file_meta.entity_tag,
    )
    return meta

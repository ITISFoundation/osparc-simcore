import logging
import re
import urllib.parse
from mimetypes import guess_type
from uuid import UUID

from fastapi import FastAPI
from models_library.api_schemas_storage import FileMetaDataArray
from models_library.api_schemas_storage import FileMetaDataGet as StorageFileMetaData
from models_library.api_schemas_storage import FileUploadSchema, PresignedLink
from models_library.generics import Envelope
from pydantic import AnyUrl
from starlette.datastructures import URL

from ..core.settings import StorageSettings
from ..models.schemas.files import File
from ..utils.client_base import BaseServiceClientApi, setup_client_instance

_logger = logging.getLogger(__name__)


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
        content_type=guess_type(filename)[0] or "application/octet-stream",
        checksum=stored_file_meta.entity_tag,
    )


class StorageApi(BaseServiceClientApi):
    #
    # All files created via the API are stored in simcore-s3 as objects with name pattern "api/{file_id}/{filename.ext}"
    #
    SIMCORE_S3_ID = 0

    async def list_files(self, user_id: int) -> list[StorageFileMetaData]:
        """Lists metadata of all s3 objects name as api/* from a given user"""
        response = await self.client.post(
            "/simcore-s3/files/metadata:search",
            params={
                "user_id": str(user_id),
                "startswith": "api/",
            },
        )
        response.raise_for_status()

        files_metadata = FileMetaDataArray(__root__=response.json()["data"] or [])
        files: list[StorageFileMetaData] = files_metadata.__root__
        return files

    async def search_files(
        self, user_id: int, file_id: UUID
    ) -> list[StorageFileMetaData]:
        # NOTE: can NOT use /locations/0/files/metadata with uuid_filter=api/ because
        # logic in storage 'wrongly' assumes that all data is associated to a project and
        # here there is no project, so it would always returns an empty
        response = await self.client.post(
            "/simcore-s3/files/metadata:search",
            params={
                "user_id": str(user_id),
                "startswith": f"api/{file_id}",
            },
        )

        files_metadata = FileMetaDataArray(__root__=response.json()["data"] or [])
        files: list[StorageFileMetaData] = files_metadata.__root__
        return files

    async def get_download_link(
        self, user_id: int, file_id: UUID, file_name: str
    ) -> AnyUrl:
        object_path = urllib.parse.quote_plus(f"api/{file_id}/{file_name}")

        response = await self.client.get(
            f"/locations/{self.SIMCORE_S3_ID}/files/{object_path}",
            params={"user_id": str(user_id)},
        )

        presigned_link: PresignedLink = PresignedLink.parse_obj(response.json()["data"])
        link: AnyUrl = presigned_link.link
        return link

    async def get_upload_links(
        self, user_id: int, file_id: UUID, file_name: str
    ) -> FileUploadSchema:
        object_path = urllib.parse.quote_plus(f"api/{file_id}/{file_name}")

        response = await self.client.put(
            f"/locations/{self.SIMCORE_S3_ID}/files/{object_path}",
            params={"user_id": user_id, "file_size": 0},
        )

        enveloped_data = Envelope[FileUploadSchema].parse_obj(response.json())
        assert enveloped_data.data  # nosec
        return enveloped_data.data

    async def generate_complete_upload_link(
        self, file: File, query: dict[str, str] | None = None
    ) -> URL:
        url = URL(
            f"{self.client.base_url}locations/{self.SIMCORE_S3_ID}/files/{file.quoted_storage_file_id}:complete"
        )
        if query is not None:
            url = url.include_query_params(**query)
        return url

    async def generate_abort_upload_link(
        self, file: File, query: dict[str, str] | None = None
    ) -> URL:
        url = URL(
            f"{self.client.base_url}locations/{self.SIMCORE_S3_ID}/files/{file.quoted_storage_file_id}:abort"
        )
        if query is not None:
            url = url.include_query_params(**query)
        return url

    async def create_soft_link(
        self, user_id: int, target_s3_path: str, as_file_id: UUID
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

        stored_file_meta = StorageFileMetaData.parse_obj(response.json()["data"])
        file_meta: File = to_file_api_model(stored_file_meta)
        return file_meta


# MODULES APP SETUP -------------------------------------------------------------


def setup(app: FastAPI, settings: StorageSettings) -> None:
    if not settings:
        settings = StorageSettings()

    setup_client_instance(
        app, StorageApi, api_baseurl=settings.api_base_url, service_name="storage"
    )


__all__: tuple[str, ...] = (
    "setup",
    "StorageApi",
    "StorageFileMetaData",
    "to_file_api_model",
)

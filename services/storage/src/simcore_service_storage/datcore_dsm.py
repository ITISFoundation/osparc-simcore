from dataclasses import dataclass

from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    DatCoreDatasetName,
    LinkType,
    UploadedPart,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, LocationName, StorageFileID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize

from .constants import DATCORE_ID, DATCORE_STR
from .dsm_factory import BaseDataManager
from .models import DatasetMetaData, FileMetaData, UploadLinks
from .modules.datcore_adapter import datcore_adapter
from .modules.datcore_adapter.datcore_adapter_exceptions import (
    DatcoreAdapterMultipleFilesError,
)
from .modules.db.tokens import get_api_token_and_secret


@dataclass
class DatCoreDataManager(BaseDataManager):
    app: FastAPI

    async def _get_datcore_tokens(self, user_id: UserID):
        return await get_api_token_and_secret(self.app, user_id)

    @classmethod
    def get_location_id(cls) -> LocationID:
        return DATCORE_ID

    @classmethod
    def get_location_name(cls) -> LocationName:
        return DATCORE_STR

    async def authorized(self, user_id: UserID) -> bool:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        if api_token and api_secret:
            return await datcore_adapter.check_user_can_connect(
                self.app, api_token, api_secret
            )
        return False

    async def list_datasets(self, user_id: UserID) -> list[DatasetMetaData]:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        return await datcore_adapter.list_datasets(self.app, api_token, api_secret)

    async def list_files_in_dataset(
        self, user_id: UserID, dataset_id: str, *, expand_dirs: bool
    ) -> list[FileMetaData]:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        return await datcore_adapter.list_all_files_metadatas_in_dataset(
            self.app, user_id, api_token, api_secret, DatCoreDatasetName(dataset_id)
        )

    async def list_files(
        self,
        user_id: UserID,
        *,
        expand_dirs: bool,
        uuid_filter: str,
        project_id: ProjectID | None,
    ) -> list[FileMetaData]:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        return await datcore_adapter.list_all_datasets_files_metadatas(
            self.app, user_id, api_token, api_secret
        )

    async def get_file(self, user_id: UserID, file_id: StorageFileID) -> FileMetaData:
        api_token, api_secret = await self._get_datcore_tokens(user_id)

        package_files = await datcore_adapter.get_package_files(
            self.app, api_token, api_secret, file_id
        )

        if not len(package_files) == 1:
            raise DatcoreAdapterMultipleFilesError(
                msg=f"{len(package_files)} files in package, this breaks the current assumption"
            )
        resp_data = package_files[0]["content"]

        return FileMetaData(
            file_uuid=file_id,
            location_id=DATCORE_ID,
            location=DATCORE_STR,
            bucket_name=resp_data["s3bucket"],
            object_name=file_id,
            file_name=resp_data["filename"],
            file_id=file_id,
            file_size=resp_data["size"],
            created_at=resp_data["createdAt"],
            last_modified=resp_data["updatedAt"],
            project_id=None,
            node_id=None,
            user_id=user_id,
            is_soft_link=False,
            sha256_checksum=None,
        )

    async def create_file_upload_links(
        self,
        user_id: UserID,
        file_id: StorageFileID,
        link_type: LinkType,
        file_size_bytes: ByteSize,
        *,
        sha256_checksum: SHA256Str | None,
        is_directory: bool,
    ) -> UploadLinks:
        raise NotImplementedError

    async def complete_file_upload(
        self,
        file_id: StorageFileID,
        user_id: UserID,
        uploaded_parts: list[UploadedPart],
    ) -> FileMetaData:
        raise NotImplementedError

    async def abort_file_upload(self, user_id: UserID, file_id: StorageFileID) -> None:
        raise NotImplementedError

    async def create_file_download_link(
        self, user_id: UserID, file_id: StorageFileID, link_type: LinkType
    ) -> AnyUrl:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        return await datcore_adapter.get_file_download_presigned_link(
            self.app, api_token, api_secret, file_id
        )

    async def delete_file(self, user_id: UserID, file_id: StorageFileID) -> None:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        await datcore_adapter.delete_file(self.app, api_token, api_secret, file_id)


def create_datcore_data_manager(app: FastAPI) -> DatCoreDataManager:
    return DatCoreDataManager(app)

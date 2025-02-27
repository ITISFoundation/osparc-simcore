import contextlib
from dataclasses import dataclass
from pathlib import Path

import arrow
from fastapi import FastAPI
from models_library.api_schemas_storage.storage_schemas import (
    DatCoreCollectionName,
    DatCoreDatasetName,
    DatCorePackageName,
    LinkType,
    UploadedPart,
)
from models_library.basic_types import SHA256Str
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, LocationName, StorageFileID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize, NonNegativeInt, TypeAdapter, ValidationError

from .constants import DATCORE_ID, DATCORE_STR
from .dsm_factory import BaseDataManager
from .exceptions.errors import DatCoreCredentialsMissingError
from .models import (
    DatasetMetaData,
    FileMetaData,
    GenericCursor,
    PathMetaData,
    TotalNumber,
    UploadLinks,
)
from .modules.datcore_adapter import datcore_adapter
from .modules.datcore_adapter.datcore_adapter_exceptions import (
    DatcoreAdapterMultipleFilesError,
)
from .modules.db.tokens import get_api_token_and_secret


def _check_api_credentials(
    api_token: str | None, api_secret: str | None
) -> tuple[str, str]:
    if not api_token or not api_secret:
        raise DatCoreCredentialsMissingError
    assert api_token is not None
    assert api_secret is not None
    return api_token, api_secret


def _is_collection(file_filter: Path) -> bool:
    with contextlib.suppress(ValidationError):
        TypeAdapter(DatCoreCollectionName).validate_python(file_filter.parts[1])
        return True
    return False


@dataclass
class DatCoreDataManager(BaseDataManager):
    app: FastAPI

    async def _get_datcore_tokens(
        self, user_id: UserID
    ) -> tuple[str | None, str | None]:
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
        api_token, api_secret = _check_api_credentials(api_token, api_secret)
        return await datcore_adapter.list_all_datasets(self.app, api_token, api_secret)

    async def list_files_in_dataset(
        self, user_id: UserID, dataset_id: str, *, expand_dirs: bool
    ) -> list[FileMetaData]:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        api_token, api_secret = _check_api_credentials(api_token, api_secret)
        return await datcore_adapter.list_all_files_metadatas_in_dataset(
            self.app, user_id, api_token, api_secret, dataset_id
        )

    async def list_paths(
        self,
        user_id: UserID,
        *,
        file_filter: Path | None,
        cursor: GenericCursor | None,
        limit: NonNegativeInt,
    ) -> tuple[list[PathMetaData], GenericCursor | None, TotalNumber | None]:
        """returns a page of the file meta data a user has access to"""
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        api_token, api_secret = _check_api_credentials(api_token, api_secret)
        if not file_filter:
            datasets, next_cursor, total = await datcore_adapter.list_datasets(
                self.app,
                api_key=api_token,
                api_secret=api_secret,
                cursor=cursor,
                limit=limit,
            )
            return (
                [
                    PathMetaData(
                        path=Path(f"{dataset.dataset_id}"),
                        display_path=Path(f"{dataset.display_name}"),
                        location_id=self.location_id,
                        location=self.location_name,
                        bucket_name="fake",
                        project_id=None,
                        node_id=None,
                        user_id=user_id,
                        created_at=arrow.utcnow().datetime,
                        last_modified=arrow.utcnow().datetime,
                        file_meta_data=None,
                    )
                    for dataset in datasets
                ],
                next_cursor,
                total,
            )
        assert len(file_filter.parts)

        if len(file_filter.parts) == 1:
            # this is looking into a dataset
            return await datcore_adapter.list_top_level_objects_in_dataset(
                self.app,
                user_id=user_id,
                api_key=api_token,
                api_secret=api_secret,
                dataset_id=TypeAdapter(DatCoreDatasetName).validate_python(
                    file_filter.parts[0]
                ),
                cursor=cursor,
                limit=limit,
            )
        assert len(file_filter.parts) == 2

        if _is_collection(file_filter):
            # this is a collection
            return await datcore_adapter.list_top_level_objects_in_collection(
                self.app,
                user_id=user_id,
                api_key=api_token,
                api_secret=api_secret,
                dataset_id=TypeAdapter(DatCoreDatasetName).validate_python(
                    file_filter.parts[0]
                ),
                collection_id=TypeAdapter(DatCoreCollectionName).validate_python(
                    file_filter.parts[1]
                ),
                cursor=cursor,
                limit=limit,
            )
        assert TypeAdapter(DatCorePackageName).validate_python(
            file_filter.parts[1]
        )  # nosec

        # only other option is a file or maybe a partial?? that would be bad
        return (
            [
                await datcore_adapter.get_package_file_as_path(
                    self.app,
                    user_id=user_id,
                    api_key=api_token,
                    api_secret=api_secret,
                    dataset_id=TypeAdapter(DatCoreDatasetName).validate_python(
                        file_filter.parts[0]
                    ),
                    package_id=TypeAdapter(DatCorePackageName).validate_python(
                        file_filter.parts[1]
                    ),
                )
            ],
            None,
            1,
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
        api_token, api_secret = _check_api_credentials(api_token, api_secret)
        return await datcore_adapter.list_all_datasets_files_metadatas(
            self.app, user_id, api_token, api_secret
        )

    async def get_file(self, user_id: UserID, file_id: StorageFileID) -> FileMetaData:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        api_token, api_secret = _check_api_credentials(api_token, api_secret)

        package_files = await datcore_adapter.get_package_files(
            self.app, api_key=api_token, api_secret=api_secret, package_id=file_id
        )

        if not len(package_files) == 1:
            raise DatcoreAdapterMultipleFilesError(
                msg=f"{len(package_files)} files in package, this breaks the current assumption"
            )

        file = package_files[0]

        return FileMetaData(
            file_uuid=file_id,
            location_id=DATCORE_ID,
            location=DATCORE_STR,
            bucket_name=file.s3_bucket,
            object_name=file_id,
            file_name=file.filename,
            file_id=file_id,
            file_size=file.size,
            created_at=file.created_at,
            last_modified=file.updated_at,
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
        api_token, api_secret = _check_api_credentials(api_token, api_secret)
        return await datcore_adapter.get_file_download_presigned_link(
            self.app, api_token, api_secret, file_id
        )

    async def delete_file(self, user_id: UserID, file_id: StorageFileID) -> None:
        api_token, api_secret = await self._get_datcore_tokens(user_id)
        api_token, api_secret = _check_api_credentials(api_token, api_secret)
        await datcore_adapter.delete_file(self.app, api_token, api_secret, file_id)


def create_datcore_data_manager(app: FastAPI) -> DatCoreDataManager:
    return DatCoreDataManager(app)

from pathlib import Path

from models_library.api_schemas_datcore_adapter.datasets import (
    DataType as DatCoreDataType,
)
from models_library.api_schemas_datcore_adapter.datasets import (
    FileMetaData as DatCoreFileMetaData,
)
from models_library.api_schemas_datcore_adapter.datasets import PackageMetaData
from models_library.api_schemas_storage.storage_schemas import DatCoreDatasetName
from models_library.users import UserID
from pydantic import ByteSize

from ...constants import DATCORE_ID, DATCORE_STR
from ...models import FileMetaData, PathMetaData


def create_fmd_from_datcore_package(
    user_id: UserID, pck_metadata: PackageMetaData
) -> FileMetaData:
    return FileMetaData(
        file_uuid=f"{pck_metadata.package_id}",
        location_id=DATCORE_ID,
        location=DATCORE_STR,
        bucket_name=pck_metadata.s3_bucket,
        object_name=f"{pck_metadata.package_id}",
        file_name=pck_metadata.name,
        file_id=pck_metadata.package_id,
        file_size=ByteSize(pck_metadata.size),
        created_at=pck_metadata.created_at,
        last_modified=pck_metadata.updated_at,
        project_id=None,
        node_id=None,
        user_id=user_id,
        is_soft_link=False,
        sha256_checksum=None,
    )


def create_fmd_from_datcore_fmd(
    user_id: UserID, dat_core_fmd: DatCoreFileMetaData
) -> FileMetaData:
    return FileMetaData(
        file_uuid=f"{dat_core_fmd.path}",
        location_id=DATCORE_ID,
        location=DATCORE_STR,
        bucket_name=dat_core_fmd.dataset_id,
        object_name=f"{dat_core_fmd.package_id}",
        file_name=dat_core_fmd.name,
        file_id=dat_core_fmd.package_id,
        file_size=ByteSize(dat_core_fmd.size),
        created_at=dat_core_fmd.created_at,
        last_modified=dat_core_fmd.last_modified_at,
        project_id=None,
        node_id=None,
        user_id=user_id,
        is_soft_link=False,
        sha256_checksum=None,
    )


def create_path_meta_data_from_datcore_package(
    user_id: UserID, dataset_id: DatCoreDatasetName, pck_metadata: PackageMetaData
) -> PathMetaData:
    return PathMetaData(
        path=Path(dataset_id) / pck_metadata.package_id,
        display_path=pck_metadata.display_path,
        location_id=DATCORE_ID,
        location=DATCORE_STR,
        bucket_name=pck_metadata.s3_bucket,
        project_id=None,
        node_id=None,
        user_id=user_id,
        created_at=pck_metadata.created_at,
        last_modified=pck_metadata.updated_at,
        file_meta_data=create_fmd_from_datcore_package(user_id, pck_metadata),
    )


def create_path_meta_data_from_datcore_fmd(
    user_id: UserID, dat_core_fmd: DatCoreFileMetaData
) -> PathMetaData:
    return PathMetaData(
        path=Path(dat_core_fmd.dataset_id) / dat_core_fmd.id,
        display_path=dat_core_fmd.path,
        location_id=DATCORE_ID,
        location=DATCORE_STR,
        bucket_name=dat_core_fmd.dataset_id,
        project_id=None,
        node_id=None,
        user_id=user_id,
        created_at=dat_core_fmd.created_at,
        last_modified=dat_core_fmd.last_modified_at,
        file_meta_data=None
        if dat_core_fmd.data_type == DatCoreDataType.FOLDER
        else create_fmd_from_datcore_fmd(user_id, dat_core_fmd),
    )

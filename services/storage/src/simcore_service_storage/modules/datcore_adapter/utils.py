from models_library.api_schemas_datcore_adapter.datasets import PackageMetaData
from models_library.users import UserID
from pydantic import ByteSize

from ...constants import DATCORE_ID, DATCORE_STR
from ...models import FileMetaData


def create_fmd_from_datcore_package(
    user_id: UserID, dat_core_fmd: PackageMetaData
) -> FileMetaData:
    return FileMetaData(
        file_uuid=f"{dat_core_fmd.package_id}",
        location_id=DATCORE_ID,
        location=DATCORE_STR,
        bucket_name=dat_core_fmd.s3_bucket,
        object_name=f"{dat_core_fmd.package_id}",
        file_name=dat_core_fmd.name,
        file_id=dat_core_fmd.package_id,
        file_size=ByteSize(dat_core_fmd.size),
        created_at=dat_core_fmd.created_at,
        last_modified=dat_core_fmd.updated_at,
        project_id=None,
        node_id=None,
        user_id=user_id,
        is_soft_link=False,
        sha256_checksum=None,
    )

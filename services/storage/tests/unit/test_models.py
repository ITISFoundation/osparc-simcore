import uuid

import pytest
from models_library.api_schemas_storage import S3BucketName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID, StorageFileID
from pydantic import TypeAdapter, ValidationError
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager


@pytest.mark.parametrize(
    "file_id",
    ["test", "test/hop", "gogo", "//file.name"],
)
def test_file_id_raises_error(file_id: str):
    with pytest.raises(ValidationError):
        TypeAdapter(StorageFileID).validate_python(file_id)


@pytest.mark.parametrize(
    "file_id",
    [
        "1c46752c-b096-11ea-a3c4-02420a00392e/e603724d-4af1-52a1-b866-0d4b792f8c4a/work.zip",
        "api/7b6b4e3d-39ae-3559-8765-4f815a49984e/tmpf_qatpzx_!...***",
        "api/6f788ad9-0ad8-3d0d-9722-72f08c24a212/output_data.json",
        "N:package:ce145b61-7e4f-470b-a113-033653e86d3d",
        "f3c9be04-2d51-4e39-beb6-f4227468880b/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_file",
        "f3c9be04-2d51-4e39-beb6-f4227468880b/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_file.ext",
        "f3c9be04-2d51-4e39-beb6-f4227468880b/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_subfolder/some_file.ext",
        "f3c9be04-2d51-4e39-beb6-f4227468880b/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_subfolder/another_subfolder/some_file.ext",
        "f3c9be04-2d51-4e39-beb6-f4227468880b/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_subfolder/another_subfolder/yet_another_one/some_file.ext",
        "api/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_file",
        "api/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_file.ext",
        "api/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_subfolder/some_file.ext",
        "api/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_subfolder/another_subfolder/some_file.ext",
        "api/cd597d18-e891-4f2b-b429-3dd42ed7de1e/some_subfolder/another_subfolder/yet_another_one/some_file.ext",
    ],
)
def test_file_id(file_id: str):
    parsed_file_id = TypeAdapter(StorageFileID).validate_python(file_id)
    assert parsed_file_id
    assert parsed_file_id == file_id


def test_fmd_build_api():
    file_id = TypeAdapter(SimcoreS3FileID).validate_python(f"api/{uuid.uuid4()}/xx.dat")
    fmd = FileMetaData.from_simcore_node(
        user_id=12,
        file_id=file_id,
        bucket=TypeAdapter(S3BucketName).validate_python("test-bucket"),
        location_id=SimcoreS3DataManager.get_location_id(),
        location_name=SimcoreS3DataManager.get_location_name(),
        sha256_checksum=None,
    )

    assert fmd.node_id
    assert not fmd.project_id
    assert fmd.file_name == "xx.dat"
    assert fmd.object_name == file_id
    assert fmd.file_uuid == file_id
    assert fmd.file_id == file_id
    assert fmd.location == SimcoreS3DataManager.get_location_name()
    assert fmd.location_id == SimcoreS3DataManager.get_location_id()
    assert fmd.bucket_name == "test-bucket"


def test_fmd_build_webapi():
    file_id = TypeAdapter(SimcoreS3FileID).validate_python(
        f"{uuid.uuid4()}/{uuid.uuid4()}/xx.dat"
    )
    fmd = FileMetaData.from_simcore_node(
        user_id=12,
        file_id=file_id,
        bucket=TypeAdapter(S3BucketName).validate_python("test-bucket"),
        location_id=SimcoreS3DataManager.get_location_id(),
        location_name=SimcoreS3DataManager.get_location_name(),
        sha256_checksum=None,
    )

    assert fmd.node_id == NodeID(file_id.split("/")[1])
    assert fmd.project_id == ProjectID(file_id.split("/")[0])
    assert fmd.file_name == "xx.dat"
    assert fmd.object_name == file_id
    assert fmd.file_uuid == file_id
    assert fmd.file_id == file_id
    assert fmd.location == SimcoreS3DataManager.get_location_name()
    assert fmd.location_id == SimcoreS3DataManager.get_location_id()
    assert fmd.bucket_name == "test-bucket"

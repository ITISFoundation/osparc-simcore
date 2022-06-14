# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import filecmp
import urllib.parse
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator, Callable, Final
from uuid import uuid4

import aioboto3
import pytest
from _pytest.fixtures import FixtureRequest
from faker import Faker
from models_library.api_schemas_storage import FileUploadLinks, FileUploadSchema
from pydantic import AnyUrl, ByteSize, parse_obj_as
from settings_library.r_clone import RCloneSettings
from simcore_sdk.node_ports_common import r_clone

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


WAIT_FOR_S3_BACKEND_TO_UPDATE: Final[float] = 1.0


# FIXTURES


@pytest.fixture(
    params=[
        f"{uuid4()}.bin",
        "some funky name.txt",
        "öä$äö2-34 no extension",
    ]
)
def file_name(request: FixtureRequest) -> str:
    return request.param


@pytest.fixture
def local_file_for_download(upload_file_dir: Path, file_name: str) -> Path:
    local_file_path = upload_file_dir / f"__local__{file_name}"
    return local_file_path


# UTILS
@asynccontextmanager
async def _get_s3_object(
    r_clone_settings: RCloneSettings, s3_path: str
) -> AsyncGenerator["aioboto3.resources.factory.s3.Object", None]:
    session = aioboto3.Session(
        aws_access_key_id=r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
        aws_secret_access_key=r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
    )
    async with session.resource(
        "s3", endpoint_url=r_clone_settings.R_CLONE_S3.S3_ENDPOINT
    ) as s3:
        s3_object = await s3.Object(
            bucket_name=r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME,
            key=s3_path.removeprefix(r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME),
        )
        yield s3_object


async def _download_s3_object(
    r_clone_settings: RCloneSettings, s3_path: str, local_path: Path
):
    await asyncio.sleep(WAIT_FOR_S3_BACKEND_TO_UPDATE)
    async with _get_s3_object(r_clone_settings, s3_path) as s3_object_in_s3:
        await s3_object_in_s3.download_file(f"{local_path}")


def _fake_upload_file_link(
    r_clone_settings: RCloneSettings, s3_object: str
) -> FileUploadSchema:
    return FileUploadSchema(
        chunk_size=ByteSize(0),
        urls=[
            parse_obj_as(
                AnyUrl,
                f"s3://{r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{urllib.parse.quote( s3_object, safe='')}",
            )
        ],
        links=FileUploadLinks(
            abort_upload=parse_obj_as(AnyUrl, "https://www.fakeabort.com"),
            complete_upload=parse_obj_as(AnyUrl, "https://www.fakecomplete.com"),
        ),
    )


# TESTS
async def test_sync_local_to_s3(
    bucket: str,
    r_clone_settings: RCloneSettings,
    file_name: str,
    create_file_of_size: Callable[[ByteSize, str], Path],
    create_valid_file_uuid: Callable[[Path], str],
    tmp_path: Path,
    faker: Faker,
) -> None:
    local_file = create_file_of_size(parse_obj_as(ByteSize, "10Mib"), file_name)
    file_uuid = create_valid_file_uuid(local_file)
    upload_file_link = _fake_upload_file_link(r_clone_settings, file_uuid)
    await r_clone.sync_local_to_s3(local_file, r_clone_settings, upload_file_link)

    local_download_file = tmp_path / faker.file_name()
    await _download_s3_object(
        r_clone_settings=r_clone_settings,
        s3_path=file_uuid,
        local_path=local_download_file,
    )
    assert local_download_file.exists()

    # check same file contents after upload and download
    assert filecmp.cmp(local_file, local_download_file)

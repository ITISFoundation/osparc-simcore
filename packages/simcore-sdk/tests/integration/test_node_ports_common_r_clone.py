# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import asyncio
import filecmp
import re
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


@pytest.fixture(
    params=[
        f"{uuid4()}.bin",
        "some funky name.txt",
        "öä$äö2-34 no extension",
    ]
)
def file_name(request: FixtureRequest) -> str:
    return request.param  # type: ignore


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
                f"s3://{r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{urllib.parse.quote(s3_object)}",
            )
        ],
        links=FileUploadLinks(
            abort_upload=parse_obj_as(AnyUrl, "https://www.fakeabort.com"),
            complete_upload=parse_obj_as(AnyUrl, "https://www.fakecomplete.com"),
        ),
    )


def test_s3_url_quote_and_unquote():
    """This test was added to validate quotation operations in _fake_upload_file_link
    against unquotation operation in

    """
    src = "53a35372-d44d-4d2e-8319-b40db5f31ce0/2f67d5cb-ea9c-4f8c-96ef-eae8445a0fe7/6fa73b0f-4006-46c6-9847-967b45ff3ae7.bin"
    # as in _fake_upload_file_link
    url = f"s3://simcore/{urllib.parse.quote(src)}"

    # as in sync_local_to_s3
    unquoted_url = urllib.parse.unquote(url)
    truncated_url = re.sub(r"^s3://", "", unquoted_url)
    assert truncated_url == f"simcore/{src}"


async def test_sync_local_to_s3(
    r_clone_settings: RCloneSettings,
    file_name: str,
    create_file_of_size: Callable[[ByteSize, str], Path],
    create_valid_file_uuid: Callable[[str, Path], str],
    tmp_path: Path,
    faker: Faker,
) -> None:
    local_file = create_file_of_size(parse_obj_as(ByteSize, "10Mib"), file_name)
    file_uuid = create_valid_file_uuid("", local_file)
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

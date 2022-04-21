# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, AsyncIterable, Dict, Iterator
from uuid import UUID

import aioboto3
import pytest
from faker import Faker
from settings_library.r_clone import RCloneSettings, S3Provider
from simcore_sdk.node_ports_v2.r_clone import is_r_clone_installed, sync_local_to_s3

pytest_simcore_core_services_selection = [
    "postgres",
]

pytest_simcore_ops_services_selection = [
    "minio",
]

# FIXTURES


@pytest.fixture
def file_name(faker: Faker) -> str:
    return f"file_{faker.uuid4()}.txt"


@pytest.fixture
def upload_file_dir(tmpdir: Path) -> Iterator[Path]:
    temp_path = Path(tmpdir)
    assert temp_path.is_dir()
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def file_to_upload(upload_file_dir: Path, file_name: str, faker: Faker) -> Path:
    # generate file with data
    file_path = upload_file_dir / file_name
    file_path.write_text(faker.paragraph(nb_sentences=5))
    return file_path


@pytest.fixture
def local_file_for_download(upload_file_dir: Path, file_name: str) -> Path:
    local_file_path = upload_file_dir / f"__local__{file_name}"
    return local_file_path


@pytest.fixture
async def r_clone_settings(minio_config: Dict[str, Any]) -> RCloneSettings:
    client = minio_config["client"]
    settings = RCloneSettings.parse_obj(
        dict(
            R_CLONE_S3=dict(
                S3_ENDPOINT=client["endpoint"],
                S3_ACCESS_KEY=client["access_key"],
                S3_SECRET_KEY=client["secret_key"],
                S3_BUCKET_NAME=minio_config["bucket_name"],
                S3_SECURE=client["secure"],
            ),
            R_CLONE_PROVIDER=S3Provider.MINIO,
        )
    )
    if not await is_r_clone_installed(settings):
        pytest.skip("rclone not installed")

    return settings


@pytest.fixture
def project_id() -> UUID:
    return UUID(int=1)


@pytest.fixture
def node_uuid() -> UUID:
    return UUID(int=2)


@pytest.fixture
def s3_object(
    r_clone_settings: RCloneSettings, project_id: UUID, node_uuid: UUID, file_name: str
) -> str:

    s3_path = (
        Path(r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME)
        / f"{project_id}"
        / f"{node_uuid}"
        / file_name
    )
    return f"{s3_path}"


@pytest.fixture
async def cleanup_s3(
    r_clone_settings: RCloneSettings, s3_object: str
) -> AsyncIterable[None]:
    yield
    async with _get_s3_object(r_clone_settings, s3_object) as s3_object:
        await s3_object.delete()


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
        "s3", endpoint_url=r_clone_settings.R_CLONE_S3.endpoint
    ) as s3:
        s3_object = await s3.Object(
            bucket_name=r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME,
            key=s3_path.lstrip(r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME),
        )
        yield s3_object


async def _download_s3_object(
    r_clone_settings: RCloneSettings, s3_path: str, local_path: Path
):
    async with _get_s3_object(r_clone_settings, s3_path) as s3_object:
        await s3_object.download_file(f"{local_path}")


# TESTS


async def test_sync_local_to_s3(
    r_clone_settings: RCloneSettings,
    s3_object: str,
    file_to_upload: Path,
    local_file_for_download: Path,
    cleanup_s3: None,
) -> None:
    etag = await sync_local_to_s3(
        r_clone_settings=r_clone_settings,
        s3_path=s3_object,
        local_file_path=file_to_upload,
    )

    assert isinstance(etag, str)
    assert '"' not in etag

    await _download_s3_object(
        r_clone_settings=r_clone_settings,
        s3_path=s3_object,
        local_path=local_file_for_download,
    )

    # check same file contents after upload and download
    assert file_to_upload.read_text() == local_file_for_download.read_text()

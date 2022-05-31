# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import shutil
from pathlib import Path
from typing import AsyncIterable, Iterator, Optional
from uuid import uuid4

import aiofiles
import aiohttp
import pytest
import sqlalchemy as sa
from _pytest.fixtures import FixtureRequest
from aiohttp import ClientSession
from faker import Faker
from pytest_mock.plugin import MockerFixture
from settings_library.r_clone import RCloneSettings
from simcore_postgres_database.models.file_meta_data import file_meta_data
from simcore_sdk.node_ports_common import r_clone
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.filemanager import (
    delete_file,
    get_download_link_from_s3,
)
from simcore_sdk.node_ports_common.storage_client import LinkType

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


class _TestException(Exception):
    pass


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
def upload_file_dir(tmp_path: Path) -> Iterator[Path]:
    assert tmp_path.is_dir()
    yield tmp_path
    shutil.rmtree(tmp_path)


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
def s3_object(project_id: str, node_uuid: str, file_name: str) -> str:
    s3_path = Path(project_id) / node_uuid / file_name
    return f"{s3_path}"


@pytest.fixture
async def cleanup_s3(s3_object: str, user_id: int) -> AsyncIterable[None]:
    yield
    await delete_file(user_id=user_id, store_id=SIMCORE_LOCATION, s3_object=s3_object)


@pytest.fixture
def raise_error_after_upload(
    mocker: MockerFixture, postgres_db: sa.engine.Engine, s3_object: str
) -> None:
    handler = r_clone._async_command  # pylint: disable=protected-access

    async def _mock_async_command(*cmd: str, cwd: Optional[str] = None) -> str:
        await handler(*cmd, cwd=cwd)
        assert _is_file_present(postgres_db=postgres_db, s3_object=s3_object) is True

        raise _TestException()

    mocker.patch(
        "simcore_sdk.node_ports_common.r_clone._async_command",
        side_effect=_mock_async_command,
    )


@pytest.fixture
async def client_session(filemanager_cfg: None) -> AsyncIterable[ClientSession]:
    async with ClientSession() as session:
        yield session


# UTILS


async def _download_s3_object(s3_path: str, local_path: Path, user_id: int):
    s3_download_link = await get_download_link_from_s3(
        user_id=user_id,
        store_name=None,
        store_id=SIMCORE_LOCATION,
        s3_object=s3_path,
        link_type=LinkType.PRESIGNED,
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(s3_download_link) as resp:
            if resp.status == 200:
                f = await aiofiles.open(local_path, mode="wb")
                await f.write(await resp.read())
                await f.close()


def _is_file_present(postgres_db: sa.engine.Engine, s3_object: str) -> bool:
    with postgres_db.begin() as conn:
        result = conn.execute(
            file_meta_data.select().where(file_meta_data.c.file_uuid == s3_object)
        )
        result_list = list(result)
        result_len = len(result_list)
    assert result_len <= 1, result_list
    return result_len == 1


# TESTS


@pytest.mark.flaky(max_runs=3)
async def test_sync_local_to_s3(
    r_clone_settings: RCloneSettings,
    s3_object: str,
    file_to_upload: Path,
    local_file_for_download: Path,
    user_id: int,
    postgres_db: sa.engine.Engine,
    client_session: ClientSession,
    cleanup_s3: None,
) -> None:

    await r_clone.sync_local_to_s3(
        session=client_session,
        r_clone_settings=r_clone_settings,
        s3_object=s3_object,
        local_file_path=file_to_upload,
        user_id=user_id,
        store_id=SIMCORE_LOCATION,
    )

    await _download_s3_object(
        s3_path=s3_object,
        local_path=local_file_for_download,
        user_id=user_id,
    )

    # check same file contents after upload and download
    assert file_to_upload.read_text() == local_file_for_download.read_text()

    assert _is_file_present(postgres_db=postgres_db, s3_object=s3_object) is True


async def test_sync_local_to_s3_cleanup_on_error(
    r_clone_settings: RCloneSettings,
    s3_object: str,
    file_to_upload: Path,
    user_id: int,
    postgres_db: sa.engine.Engine,
    client_session: ClientSession,
    cleanup_s3: None,
    raise_error_after_upload: None,
) -> None:
    with pytest.raises(_TestException):
        await r_clone.sync_local_to_s3(
            session=client_session,
            r_clone_settings=r_clone_settings,
            s3_object=s3_object,
            local_file_path=file_to_upload,
            user_id=user_id,
            store_id=SIMCORE_LOCATION,
        )
    assert _is_file_present(postgres_db=postgres_db, s3_object=s3_object) is False

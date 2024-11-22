# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument


import filecmp
import os
import shutil
from collections.abc import AsyncIterable, Iterable
from pathlib import Path
from typing import Final, cast
from unittest.mock import AsyncMock

import aioboto3
import pytest
import sqlalchemy as sa
from aiobotocore.session import ClientCreatorContext
from async_asgi_testclient import TestClient
from botocore.client import Config
from botocore.exceptions import ClientError
from fastapi import FastAPI
from models_library.api_schemas_storage import S3BucketName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from models_library.users import UserID
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.faker_factories import random_project
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import PostgresTestConfig
from pytest_simcore.helpers.storage import replace_storage_endpoint
from servicelib.fastapi.long_running_tasks.server import TaskProgress
from servicelib.utils import logged_gather
from settings_library.s3 import S3Settings
from simcore_postgres_database.models.projects import projects
from simcore_sdk.node_ports_common.constants import SIMCORE_LOCATION
from simcore_sdk.node_ports_common.filemanager import upload_path
from simcore_service_dynamic_sidecar.core.application import AppState, create_app
from simcore_service_dynamic_sidecar.core.utils import HIDDEN_FILE_NAME
from simcore_service_dynamic_sidecar.modules.long_running_tasks import (
    task_restore_state,
    task_save_state,
)
from types_aiobotocore_s3 import S3Client
from yarl import URL

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
    "storage",
    "redis",
]

pytest_simcore_ops_services_selection = [
    "minio",
    "adminer",
]


TO_REMOVE: set[Path] = {Path(HIDDEN_FILE_NAME)}


@pytest.fixture
def project_id(user_id: int, postgres_db: sa.engine.Engine) -> Iterable[ProjectID]:
    # inject project for user in db. This will give user_id, the full project's ownership

    # pylint: disable=no-value-for-parameter
    stmt = (
        projects.insert()
        .values(**random_project(prj_owner=user_id))
        .returning(projects.c.uuid)
    )
    print(f"{stmt}")
    with postgres_db.connect() as conn:
        result = conn.execute(stmt)
        row = result.first()
        assert row
        prj_uuid = row[projects.c.uuid]

    yield prj_uuid

    with postgres_db.connect() as conn:
        conn.execute(projects.delete().where(projects.c.uuid == prj_uuid))


@pytest.fixture
def mock_environment(
    mock_storage_check: None,
    mock_rabbit_check: None,
    postgres_host_config: PostgresTestConfig,
    storage_endpoint: URL,
    minio_s3_settings_envs: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    base_mock_envs: EnvVarsDict,
    user_id: UserID,
    project_id: ProjectID,
) -> EnvVarsDict:
    assert storage_endpoint.host

    envs: EnvVarsDict = {
        "STORAGE_HOST": storage_endpoint.host,
        "STORAGE_PORT": f"{storage_endpoint.port}",
        "DY_SIDECAR_USER_ID": f"{user_id}",
        "DY_SIDECAR_PROJECT_ID": f"{project_id}",
        "R_CLONE_PROVIDER": "MINIO",
        "DY_SIDECAR_CALLBACKS_MAPPING": "{}",
        "RABBIT_HOST": "test",
        "RABBIT_PASSWORD": "test",
        "RABBIT_SECURE": "0",
        "RABBIT_USER": "test",
        **base_mock_envs,
    }

    setenvs_from_dict(monkeypatch, envs)
    return envs


@pytest.fixture
def app(
    mock_environment: EnvVarsDict,
    mock_registry_service: AsyncMock,
    mock_core_rabbitmq: dict[str, AsyncMock],
) -> FastAPI:
    """creates app with registry and rabbitMQ services mocked"""
    return create_app()


@pytest.fixture
async def test_client(app: FastAPI) -> AsyncIterable[TestClient]:
    async with TestClient(app) as client:
        yield client


@pytest.fixture
def task_progress() -> TaskProgress:
    return TaskProgress.create()


@pytest.fixture
def app_state(app: FastAPI) -> AppState:
    return AppState(app)


@pytest.fixture
def state_paths_to_legacy_archives(
    app_state: AppState, project_tests_dir: Path
) -> dict[Path, Path]:
    LEGACY_STATE_ARCHIVES_DIR = project_tests_dir / "mocks" / "legacy_state_archives"
    assert LEGACY_STATE_ARCHIVES_DIR.exists()

    results: dict[Path, Path] = {}
    for state_path in app_state.mounted_volumes.disk_state_paths_iter():
        legacy_archive_name = f"{state_path.name}.zip"
        legacy_archive_path = LEGACY_STATE_ARCHIVES_DIR / legacy_archive_name
        assert legacy_archive_path.exists()
        results[state_path] = legacy_archive_path

    return results


@pytest.fixture
async def simcore_storage_service(mocker: MockerFixture, app: FastAPI) -> None:
    storage_host: Final[str] | None = os.environ.get("STORAGE_HOST")
    storage_port: Final[str] | None = os.environ.get("STORAGE_PORT")
    assert storage_host is not None
    assert storage_port is not None

    # NOTE: Mock to ensure container IP agrees with host IP when testing
    mocker.patch(
        "simcore_sdk.node_ports_common._filemanager._get_https_link_if_storage_secure",
        replace_storage_endpoint(storage_host, int(storage_port)),
    )


@pytest.fixture
async def restore_legacy_state_archives(
    test_client: TestClient,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    state_paths_to_legacy_archives: dict[Path, Path],
) -> None:

    tasks = []
    for legacy_archive_zip in state_paths_to_legacy_archives.values():
        s3_path = f"{project_id}/{node_id}/{legacy_archive_zip.name}"
        tasks.append(
            upload_path(
                user_id=user_id,
                store_id=SIMCORE_LOCATION,
                store_name=None,
                s3_object=TypeAdapter(SimcoreS3FileID).validate_python(s3_path),
                path_to_upload=legacy_archive_zip,
                io_log_redirect_cb=None,
            )
        )

    await logged_gather(*tasks)


def _generate_content(root_path: Path, *, file_prefix: str, payload: str = "a") -> None:
    # NOTE: this was also used to generate the content of the zips
    # stored inside `mocks/legacy_state_archives` directory
    # NOTE: changing this function's outcome requires the
    # regeneration of the zip archives
    assert root_path.exists()

    paths: set[Path] = {
        root_path / "s" / "u" / "b" / "d" / "i" / "r" / "s",
        root_path / "first-level",
        root_path / "111",
        root_path / "dir.txt",
        root_path,
    }

    file_names: set[str] = {f"{file_prefix}_file-{i}.txt" for i in range(10)}

    for path in paths:
        for file_name in file_names:
            path.mkdir(parents=True, exist_ok=True)
            (path / file_name).write_text(payload)


@pytest.fixture
def expected_contents_paths(app_state: AppState, tmp_path: Path) -> dict[Path, Path]:
    results: dict[Path, Path] = {}

    expected_contents_dir = tmp_path / "expected_contents"

    for k, state_path in enumerate(app_state.mounted_volumes.disk_state_paths_iter()):
        expected_state_path_dir = expected_contents_dir / state_path.name
        expected_state_path_dir.mkdir(parents=True, exist_ok=True)
        _generate_content(expected_state_path_dir, file_prefix=f"{k}_")
        results[state_path] = expected_state_path_dir

    return results


def _files_in_dir(
    dir_path: Path,
    *,
    include_parent_dir_name: bool = False,
    discard: set[Path] | None = None,
) -> set[Path]:
    parent_dir_name = dir_path.name if include_parent_dir_name else ""
    result = {
        Path(parent_dir_name) / p.relative_to(dir_path)
        for p in dir_path.rglob("*")
        if p.is_file()
    }

    if discard is None:
        return result

    for entry in discard:
        result.discard(Path(parent_dir_name) / entry)
    return result


def _delete_files_in_dir(dir_path: Path) -> None:
    for file in _files_in_dir(dir_path):
        (dir_path / file).unlink()


def _assert_same_directory_content(dir1: Path, dir2: Path) -> None:
    # NOTE: the HIDDEN_FILE_NAME is added automatically by the dy-sidecar
    # when it initializes, this is added below just for the comparison

    files_in_dir1 = _files_in_dir(dir1, discard=TO_REMOVE)
    files_in_dir2 = _files_in_dir(dir2, discard=TO_REMOVE)

    all_files_in_both_dirs = files_in_dir1 & files_in_dir2

    # ensure files overlap
    assert len(files_in_dir1) > 0, "Expected at least one file!"
    assert len(all_files_in_both_dirs) == len(files_in_dir1)
    assert len(all_files_in_both_dirs) == len(files_in_dir2)

    for file in all_files_in_both_dirs:
        f_in_dir1 = dir1 / file
        f_in_dir2 = dir2 / file

        assert f_in_dir1.exists()
        assert f_in_dir2.exists()

        assert filecmp.cmp(f_in_dir1, f_in_dir2, shallow=False)


@pytest.fixture
def s3_settings(app_state: AppState) -> S3Settings:
    return app_state.settings.DY_SIDECAR_R_CLONE_SETTINGS.R_CLONE_S3


@pytest.fixture
def bucket_name(app_state: AppState) -> S3BucketName:
    return TypeAdapter(S3BucketName).validate_python(
        app_state.settings.DY_SIDECAR_R_CLONE_SETTINGS.R_CLONE_S3.S3_BUCKET_NAME,
    )


@pytest.fixture
async def s3_client(s3_settings: S3Settings) -> AsyncIterable[S3Client]:
    session = aioboto3.Session()
    session_client = session.client(
        "s3",
        endpoint_url=f"{s3_settings.S3_ENDPOINT}",
        aws_access_key_id=s3_settings.S3_ACCESS_KEY,
        aws_secret_access_key=s3_settings.S3_SECRET_KEY,
        region_name=s3_settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )
    assert isinstance(session_client, ClientCreatorContext)  # nosec
    async with session_client as client:
        client = cast(S3Client, client)
        yield client


async def _is_key_in_s3(
    s3_client: S3Client, bucket_name: S3BucketName, key: str
) -> bool:
    try:
        await s3_client.head_object(Bucket=bucket_name, Key=key)
    except ClientError:
        return False
    return True


async def _assert_keys_in_s3(
    s3_client: S3Client,
    bucket_name: S3BucketName,
    keys: list[str],
    *,
    each_key_is_in_s3: bool,
) -> None:
    keys_exist_in_s3 = await logged_gather(
        *[
            _is_key_in_s3(s3_client=s3_client, bucket_name=bucket_name, key=key)
            for key in keys
        ]
    )
    results: dict[str, bool] = dict(zip(keys, keys_exist_in_s3, strict=True))
    for key, key_exists in results.items():
        assert (
            key_exists is each_key_is_in_s3
        ), f"Unexpected result: {key_exists=} != {each_key_is_in_s3=} for '{key}'\nAll results: {results}"


def _get_expected_s3_objects(
    project_id: ProjectID, node_id: NodeID, state_dirs: list[Path]
) -> list[str]:
    result: set[Path] = set()
    for state_path in state_dirs:
        result |= _files_in_dir(state_path, include_parent_dir_name=True)
    return [f"{project_id}/{node_id}/{x}" for x in result]


@pytest.mark.parametrize("repeat_count", [1, 2])
async def test_legacy_state_open_and_clone(
    simcore_storage_service: None,
    restore_legacy_state_archives: None,
    state_paths_to_legacy_archives: dict[Path, Path],
    expected_contents_paths: dict[Path, Path],
    app: FastAPI,
    app_state: AppState,
    task_progress: TaskProgress,
    project_id: ProjectID,
    node_id: NodeID,
    s3_client: S3Client,
    bucket_name: S3BucketName,
    repeat_count: int,
):
    # NOTE: this tests checks that the legacy state is migrated to the new style state

    # restore state from legacy archives
    for _ in range(repeat_count):
        await task_restore_state(
            progress=task_progress,
            settings=app_state.settings,
            mounted_volumes=app_state.mounted_volumes,
            app=app,
        )

    # check that legacy and generated folder content is the same
    for state_dir_path, expected_content_dir_path in expected_contents_paths.items():
        _assert_same_directory_content(state_dir_path, expected_content_dir_path)

    # check that the file is still present in storage s3
    legacy_s3_keys: list[str] = [
        f"{project_id}/{node_id}/{legacy_archive_path.name}"
        for legacy_archive_path in state_paths_to_legacy_archives.values()
    ]
    await _assert_keys_in_s3(
        s3_client, bucket_name, keys=legacy_s3_keys, each_key_is_in_s3=True
    )

    for _ in range(repeat_count):
        await task_save_state(
            progress=task_progress,
            settings=app_state.settings,
            mounted_volumes=app_state.mounted_volumes,
            app=app,
        )

    # check that all local files are present in s3
    expected_s3_objects = _get_expected_s3_objects(
        project_id, node_id, list(expected_contents_paths.keys())
    )
    await _assert_keys_in_s3(
        s3_client, bucket_name, keys=expected_s3_objects, each_key_is_in_s3=True
    )

    # the legacy archives should now be missing
    await _assert_keys_in_s3(
        s3_client, bucket_name, keys=legacy_s3_keys, each_key_is_in_s3=False
    )


@pytest.mark.parametrize("repeat_count", [1, 2])
async def test_state_open_and_close(
    simcore_storage_service: None,
    test_client: TestClient,
    state_paths_to_legacy_archives: dict[Path, Path],
    expected_contents_paths: dict[Path, Path],
    app: FastAPI,
    app_state: AppState,
    task_progress: TaskProgress,
    project_id: ProjectID,
    node_id: NodeID,
    s3_client: S3Client,
    bucket_name: S3BucketName,
    repeat_count: int,
):
    # NOTE: this is the new style of opening and closing the state using directories

    # restoring finds nothing inside
    for _ in range(repeat_count):
        await task_restore_state(
            progress=task_progress,
            settings=app_state.settings,
            mounted_volumes=app_state.mounted_volumes,
            app=app,
        )

    # check that no other objects are in s3
    expected_s3_objects = _get_expected_s3_objects(
        project_id, node_id, list(expected_contents_paths.keys())
    )
    await _assert_keys_in_s3(
        s3_client, bucket_name, keys=expected_s3_objects, each_key_is_in_s3=False
    )

    # check that no files are present in the local directories
    for state_dir_path in expected_contents_paths:
        assert len(_files_in_dir(state_dir_path, discard=TO_REMOVE)) == 0

    # copy the content to be generated to the local folder
    for state_dir_path, expected_content_dir_path in expected_contents_paths.items():
        shutil.copytree(expected_content_dir_path, state_dir_path, dirs_exist_ok=True)
        _assert_same_directory_content(state_dir_path, expected_content_dir_path)

    # save them to S3
    for _ in range(repeat_count):
        await task_save_state(
            progress=task_progress,
            settings=app_state.settings,
            mounted_volumes=app_state.mounted_volumes,
            app=app,
        )

    # check generated files are in S3
    expected_s3_objects = _get_expected_s3_objects(
        project_id, node_id, list(expected_contents_paths.keys())
    )
    assert len(expected_s3_objects) > 0
    await _assert_keys_in_s3(
        s3_client, bucket_name, keys=expected_s3_objects, each_key_is_in_s3=True
    )

    # remove and check no file is present any longer
    for state_dir_path in expected_contents_paths:
        _delete_files_in_dir(state_dir_path)
        assert len(_files_in_dir(state_dir_path, discard=TO_REMOVE)) == 0

    # restore them from S3
    for _ in range(repeat_count):
        await task_restore_state(
            progress=task_progress,
            settings=app_state.settings,
            mounted_volumes=app_state.mounted_volumes,
            app=app,
        )

    # check files are the same as the ones previously generated
    for state_dir_path, expected_content_dir_path in expected_contents_paths.items():
        _assert_same_directory_content(state_dir_path, expected_content_dir_path)

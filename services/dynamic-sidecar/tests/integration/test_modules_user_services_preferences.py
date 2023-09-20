# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=no-name-in-module

from collections.abc import AsyncIterable
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import parse_obj_as
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.utils_postgres import PostgresTestConfig
from simcore_service_dynamic_sidecar.core.application import create_app
from simcore_service_dynamic_sidecar.modules.user_services_preferences import (
    load_user_services_preferences,
    save_user_services_preferences,
)
from simcore_service_dynamic_sidecar.modules.user_services_preferences._utils import (
    is_feature_enabled,
)

pytest_plugins = [
    "pytest_simcore.postgres_service",
]

pytest_simcore_core_services_selection = [
    "migration",
    "postgres",
]

pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def user_preferences_path(tmp_path: Path) -> Path:
    preferences_path = tmp_path / "user_prefernces"
    preferences_path.mkdir(parents=True, exist_ok=True)
    assert preferences_path.is_dir()
    assert preferences_path.exists()
    return preferences_path


@pytest.fixture
def service_key() -> ServiceKey:
    return parse_obj_as(ServiceKey, "simcore/services/dynamic/test-service-34")


@pytest.fixture
def service_version() -> ServiceVersion:
    return parse_obj_as(ServiceVersion, "1.0.0")


@pytest.fixture
def product_name() -> ProductName:
    return parse_obj_as(ProductName, "osparc")


@pytest.fixture
def mock_environment(
    postgres_host_config: PostgresTestConfig,
    monkeypatch: pytest.MonkeyPatch,
    base_mock_envs: EnvVarsDict,
    user_id: UserID,
    project_id: ProjectID,
    user_preferences_path: Path,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    product_name: ProductName,
) -> EnvVarsDict:
    envs: EnvVarsDict = {
        "DY_SIDECAR_USER_ID": f"{user_id}",
        "DY_SIDECAR_PROJECT_ID": f"{project_id}",
        "S3_ENDPOINT": "test",
        "S3_ACCESS_KEY": "test",
        "S3_SECRET_KEY": "test",
        "S3_BUCKET_NAME": "test",
        "S3_SECURE": "false",
        "R_CLONE_PROVIDER": "MINIO",
        "DY_SIDECAR_CALLBACKS_MAPPING": "{}",
        "DY_SIDECAR_SERVICE_KEY": service_key,
        "DY_SIDECAR_SERVICE_VERSION": service_version,
        "DY_SIDECAR_USER_PREFERENCES_PATH": f"{user_preferences_path}",
        "DY_SIDECAR_PRODUCT_NAME": product_name,
        **base_mock_envs,
    }

    setenvs_from_dict(monkeypatch, envs)
    return envs


@pytest.fixture
async def app(
    mock_environment: EnvVarsDict,
    mock_registry_service: AsyncMock,
    mock_core_rabbitmq: dict[str, AsyncMock],
) -> AsyncIterable[FastAPI]:
    app = create_app()
    async with LifespanManager(app):
        yield app


def _get_files_preferences_path(user_preferences_path: Path) -> set[Path]:
    return {x for x in user_preferences_path.rglob("*") if x.is_file()}


def _make_files_in_preferences_path(
    user_preferences_path: Path, file_count: int, subdir_count: int
) -> set[Path]:
    file_names: set[Path] = set()
    for s in range(subdir_count):
        (user_preferences_path / f"subdir-{s}").mkdir(parents=True, exist_ok=True)
        for f in range(file_count):
            file_name = user_preferences_path / f"subdir-{s}" / f"f{f}.txt"
            file_name.write_text(f"file content {f}")
            file_names.add(file_name)
    return file_names


def _remove_files_in_preferences_path(user_preferences_path: Path):
    for f in user_preferences_path.rglob("*"):
        if f.is_file():
            f.unlink()


async def test_user_service_workflow(app: FastAPI, user_preferences_path: Path):
    assert is_feature_enabled(app)

    # restore nothing is downloaded
    await load_user_services_preferences(app)
    assert len(_get_files_preferences_path(user_preferences_path)) == 0

    # mock user service creates some preferences
    FILE_COUNT = 4
    SUBDIR_COUNT = 2
    file_names = _make_files_in_preferences_path(
        user_preferences_path, FILE_COUNT, SUBDIR_COUNT
    )
    assert _get_files_preferences_path(user_preferences_path) == file_names

    # save preferences to be recovered at later date
    await save_user_services_preferences(app)

    # mock service was closed
    _remove_files_in_preferences_path(user_preferences_path)
    assert len(_get_files_preferences_path(user_preferences_path)) == 0

    # reopen service which had saved preferences
    await load_user_services_preferences(app)
    assert _get_files_preferences_path(user_preferences_path) == file_names


# TODO: do something with the versions, one before and one after, check that the settings are restorted or not as expected

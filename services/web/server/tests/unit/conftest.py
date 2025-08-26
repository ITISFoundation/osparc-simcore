# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import sys
from collections.abc import AsyncIterator, Callable, Iterable
from pathlib import Path
from typing import Any

import pytest
import yaml
from aiohttp.test_utils import TestClient
from models_library.products import ProductName
from pytest_mock import MockFixture, MockType
from pytest_simcore.helpers.webserver_projects import NewProject, empty_project_data
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.application_settings_utils import AppConfigDict
from simcore_service_webserver.constants import FRONTEND_APP_DEFAULT
from simcore_service_webserver.projects.models import ProjectDict

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def here() -> Path:
    cdir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    assert cdir == CURRENT_DIR, "Somebody changing current_dir?"
    return cdir


@pytest.fixture(scope="session")
def api_version_prefix() -> str:
    return "v0"


@pytest.fixture(scope="session")
def default_app_config_unit_file(tests_data_dir: Path) -> Path:
    cfg_path = tests_data_dir / "default_app_config-unit.yaml"
    assert cfg_path.exists()
    return cfg_path


@pytest.fixture(scope="session")
def default_app_cfg(default_app_config_unit_file: Path) -> AppConfigDict:
    # NOTE: ONLY used at the session scopes
    # TODO: create instead a loader function and return a Callable
    config: dict = yaml.safe_load(default_app_config_unit_file.read_text())
    return config


@pytest.fixture
def empty_project() -> Callable:
    def factory():
        return empty_project_data()

    return factory


@pytest.fixture
def activity_data(fake_data_dir: Path) -> Iterable[dict[str, Any]]:
    with (fake_data_dir / "test_activity_data.json").open() as fp:
        yield json.load(fp)


@pytest.fixture
def mock_orphaned_services(mocker: MockFixture) -> MockType:
    return mocker.patch(
        "simcore_service_webserver.garbage_collector._core.remove_orphaned_services",
        return_value="",
    )


@pytest.fixture
def disable_gc_manual_guest_users(mocker: MockFixture) -> None:
    """Disable to avoid an almost instant cleanup of GUEST users with their projects"""
    mocker.patch(
        "simcore_service_webserver.garbage_collector._core.remove_users_manually_marked_as_guests",
        return_value=None,
    )


@pytest.fixture
def disabled_setup_garbage_collector(mocker: MockFixture) -> MockType:
    # WARNING: add it BEFORE `client` to have effect
    return mocker.patch(
        "simcore_service_webserver.application.setup_garbage_collector",
        autospec=True,
        return_value=False,
    )


@pytest.fixture(scope="session")
def product_name() -> ProductName:
    return ProductName(FRONTEND_APP_DEFAULT)


@pytest.fixture
async def user_project(
    client: TestClient,
    fake_project: ProjectDict,
    logged_user: UserInfoDict,
    tests_data_dir: Path,
    osparc_product_name: str,
) -> AsyncIterator[ProjectDict]:
    async with NewProject(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as project:
        print("-----> added project", project["name"])
        yield project
        print("<----- removed project", project["name"])

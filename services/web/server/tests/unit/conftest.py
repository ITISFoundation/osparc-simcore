""" Configuration for unit testing

    - Any interaction with other app MUST be emulated with fakes/mocks
    - ONLY external apps allowed is postgress (see unit/with_postgres)
"""

# pylint: disable=unused-argument
# pylint: disable=bare-except
# pylint:disable=redefined-outer-name

import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable

import pytest
import yaml
from openapi_core.schema.specs.models import Spec
from pytest_simcore.helpers.utils_projects import empty_project_data
from servicelib.openapi import openapi_core
from simcore_service_webserver._meta import api_vtag
from simcore_service_webserver.resources import resources

## current directory
current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

## Log
log = logging.getLogger(__name__)

pytest_plugins = [
    "pytest_simcore.environment_configs",
    "pytest_simcore.monkeypatch_extra",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.services_api_mocks_for_aiohttp_clients",
    "pytest_simcore.websocket_client",
]


@pytest.fixture(scope="session")
def here() -> Path:
    cdir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    assert cdir == current_dir, "Somebody changing current_dir?"
    return cdir


@pytest.fixture(scope="session")
def api_version_prefix() -> str:
    return "v0"


@pytest.fixture
def empty_project() -> Callable:
    def factory():
        return empty_project_data()

    return factory


@pytest.fixture
def project_schema_file(api_version_prefix) -> Path:
    prj_schema_path = resources.get_path(
        f"api/{api_version_prefix}/schemas/project-v0.0.1.json"
    )
    assert prj_schema_path.exists()
    return prj_schema_path


@pytest.fixture
def activity_data(fake_data_dir: Path) -> Iterable[Dict[str, Any]]:
    with (fake_data_dir / "test_activity_data.json").open() as fp:
        yield json.load(fp)


@pytest.fixture
def test_tags_data(fake_data_dir: Path) -> Iterable[Dict[str, Any]]:
    with (fake_data_dir / "test_tags_data.json").open() as fp:
        yield json.load(fp).get("added_tags")


@pytest.fixture
def mock_orphaned_services(mocker):
    remove_orphaned_services = mocker.patch(
        "simcore_service_webserver.resource_manager.garbage_collector.remove_orphaned_services",
        return_value="",
    )
    return remove_orphaned_services


@pytest.fixture
def disable_gc_manual_guest_users(mocker):
    """Disable to avoid an almost instant cleanup of GUEST users with their projects"""
    mocker.patch(
        "simcore_service_webserver.resource_manager.garbage_collector.remove_users_manually_marked_as_guests",
        return_value=None,
    )


@pytest.fixture(scope="session")
def openapi_specs() -> Spec:
    spec_path: Path = resources.get_path(f"api/{api_vtag}/openapi.yaml")
    spec_dict: Dict[str, Any] = yaml.safe_load(spec_path.read_text())
    api_specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())
    return api_specs

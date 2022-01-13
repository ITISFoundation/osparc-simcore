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
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pytest_simcore.helpers.utils_projects import empty_project_data
from simcore_service_webserver.resources import resources
from simcore_service_webserver.rest import get_openapi_specs_path, load_openapi_specs

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def here() -> Path:
    cdir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
    assert cdir == CURRENT_DIR, "Somebody changing current_dir?"
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


@pytest.fixture
def openapi_specs(api_version_prefix) -> OpenApiSpecs:
    spec_path = get_openapi_specs_path(api_version_prefix)
    return load_openapi_specs(spec_path)

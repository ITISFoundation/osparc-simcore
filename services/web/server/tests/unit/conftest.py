""" Configuration for unit testing

    - Any interaction with other app MUST be emulated with fakes/mocks
    - ONLY external apps allowed is postgress (see unit/with_postgres)
"""

# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Iterable

import pytest
import yaml
from models_library.projects import Project
from openapi_core.schema.specs.models import Spec as OpenApiSpecs
from pytest_simcore.helpers.utils_dict import ConfigDict
from pytest_simcore.helpers.utils_projects import empty_project_data
from simcore_service_webserver.rest._utils import (
    get_openapi_specs_path,
    load_openapi_specs,
)

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


@pytest.fixture(scope="session")
def default_app_config_unit_file(tests_data_dir: Path) -> Path:
    cfg_path = tests_data_dir / "default_app_config-unit.yaml"
    assert cfg_path.exists()
    return cfg_path


@pytest.fixture(scope="session")
def default_app_cfg(default_app_config_unit_file: Path) -> ConfigDict:
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
def mock_orphaned_services(mocker):
    remove_orphaned_services = mocker.patch(
        "simcore_service_webserver.garbage_collector_core.remove_orphaned_services",
        return_value="",
    )
    return remove_orphaned_services


@pytest.fixture
def disable_gc_manual_guest_users(mocker):
    """Disable to avoid an almost instant cleanup of GUEST users with their projects"""
    mocker.patch(
        "simcore_service_webserver.garbage_collector_core.remove_users_manually_marked_as_guests",
        return_value=None,
    )


@pytest.fixture
def openapi_specs(api_version_prefix) -> OpenApiSpecs:
    spec_path = get_openapi_specs_path(api_version_prefix)
    return load_openapi_specs(spec_path)


@pytest.fixture
def project_jsonschema() -> dict[str, Any]:
    return Project.schema(by_alias=True)

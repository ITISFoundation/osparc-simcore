# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
import sys
from collections.abc import Callable, Iterable
from functools import lru_cache
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import jsonref
import pytest
import yaml
from pytest_simcore.helpers.dict_tools import ConfigDict
from pytest_simcore.helpers.webserver_projects import empty_project_data
from simcore_service_webserver.rest._utils import get_openapi_specs_path

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
def mock_orphaned_services(mocker) -> MagicMock:
    return mocker.patch(
        "simcore_service_webserver.garbage_collector._core.remove_orphaned_services",
        return_value="",
    )


@pytest.fixture
def disable_gc_manual_guest_users(mocker):
    """Disable to avoid an almost instant cleanup of GUEST users with their projects"""
    mocker.patch(
        "simcore_service_webserver.garbage_collector._core.remove_users_manually_marked_as_guests",
        return_value=None,
    )


@lru_cache  # ANE: required to boost tests speed, gains 3.5s per test
def _load_openapi_specs(spec_path: Path | None = None) -> dict:
    if spec_path is None:
        spec_path = get_openapi_specs_path()

    with spec_path.open() as fh:
        spec_dict = yaml.safe_load(fh)

    # SEE https://jsonref.readthedocs.io/en/latest/#lazy-load-and-load-on-repr
    openapi: dict = jsonref.replace_refs(
        spec_dict, base_uri=spec_path.as_uri(), lazy_load=True, merge_props=False
    )
    return openapi


@pytest.fixture
def openapi_specs(api_version_prefix) -> dict:

    spec_path = get_openapi_specs_path(api_version_prefix)
    return _load_openapi_specs(spec_path)

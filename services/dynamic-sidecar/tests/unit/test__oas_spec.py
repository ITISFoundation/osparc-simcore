# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers.utils_envs import EnvVarsDict


@pytest.fixture
def mock_environment(mock_environment_with_envdevel: EnvVarsDict) -> None:
    # serialized openapi.json is produce with .env-devel from the project
    assert mock_environment_with_envdevel


def test_openapi_spec(
    mock_environment: None, app: FastAPI, project_slug_dir: Path
) -> None:
    spec_from_app = app.openapi()
    open_api_json_file = project_slug_dir / "openapi.json"
    stored_openapi_json_file = json.loads(open_api_json_file.read_text())
    assert (
        spec_from_app == stored_openapi_json_file
    ), "make sure to run `make openapi.json`"

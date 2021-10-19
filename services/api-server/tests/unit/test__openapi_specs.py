# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi import FastAPI


@pytest.fixture
def app_light(monkeypatch, environment) -> FastAPI:
    # patching environs
    for key, value in environment.items():
        monkeypatch.setenv(key, value)

    monkeypatch.setenv("API_SERVER_POSTGRES", "null")
    monkeypatch.setenv("API_SERVER_WEBSERVER", "null")
    monkeypatch.setenv("API_SERVER_CATALOG", "null")
    monkeypatch.setenv("API_SERVER_STORAGE", "null")
    monkeypatch.setenv("API_SERVER_DIRECTOR_V2", "null")
    monkeypatch.setenv("API_SERVER_DEV_FEATURES_ENABLED", "1")

    from simcore_service_api_server.core.application import init_app

    app = init_app()
    return app


def test_app_api_against_openapi_specifications(
    app_light: FastAPI, openapi_specs_file_path: Path, tmp_path: Path
) -> None:

    # creates comparison dir to drop both openapi.yaml
    common_dir = tmp_path / "specs"
    common_dir.mkdir(parents=True, exist_ok=True)

    implemented_api = common_dir / "openapi-server.yaml"
    with implemented_api.open("wt") as fh:
        yaml.safe_dump(app_light.openapi(), fh, sort_keys=False)

    expected_api = common_dir / "openapi-specs.yaml"
    shutil.copy(openapi_specs_file_path, expected_api)

    # Uses https://github.com/OpenAPITools/openapi-diff
    # TODO: add as helper in pytest-simcore to be used everywhere
    completion = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--volume",
            f"{common_dir}:/specs:ro",
            "openapitools/openapi-diff:latest",
            "--fail-on-incompatible",
            "--info",
            f"/specs/{expected_api.name}",
            f"/specs/{implemented_api.name}",
        ],
        check=False,
        capture_output=True,
    )

    print("Running", " ".join(completion.args))

    assert (
        completion.returncode == os.EX_OK
    ), f"{' '.join(completion.args)}:\n {completion.stdout.decode('utf-8')}"

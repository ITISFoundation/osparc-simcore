# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict, Iterator

import pytest
import simcore_service_catalog
from _pytest.monkeypatch import MonkeyPatch
from fastapi import FastAPI
from simcore_service_catalog.core.application import init_app
from starlette.testclient import TestClient

pytest_plugins = [
    "pytest_simcore.docker_compose",
    "pytest_simcore.docker_registry",
    "pytest_simcore.docker_swarm",
    "pytest_simcore.environment_configs",
    "pytest_simcore.postgres_service",
    "pytest_simcore.pydantic_models",
    "pytest_simcore.repository_paths",
    "pytest_simcore.schemas",
    "pytest_simcore.tmp_path_extra",
]


current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


## FOLDER LAYOUT ---------------------------------------------------------------------


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = current_dir.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_catalog"))
    return folder


@pytest.fixture(scope="session")
def package_dir() -> Path:
    """Notice that this might be under src (if installed as edit mode)
    or in the installation folder
    """
    dirpath = Path(simcore_service_catalog.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


# FAKE DATA ------


@pytest.fixture()
def fake_data_dag_in() -> Dict:
    DAG_DATA_IN_DICT = {
        "key": "simcore/services/frontend/nodes-group/macros/1",
        "version": "1.0.0",
        "name": "string",
        "description": "string",
        "contact": "user@example.com",
        "workbench": {
            "additionalProp1": {
                "key": "simcore/services/comp/sleeper",
                "version": "6.2.0",
                "label": "string",
                "progress": 0,
                "thumbnail": "https://string.com",
                "inputs": {},
                "inputAccess": {
                    "additionalProp1": "ReadAndWrite",
                    "additionalProp2": "ReadAndWrite",
                    "additionalProp3": "ReadAndWrite",
                },
                "inputNodes": ["ba8e4558-1088-49b1-8fe6-f591634089e5"],
                "outputs": {},
                "outputNodes": ["ba8e4558-1088-49b1-8fe6-f591634089e5"],
                "parent": "ba8e4558-1088-49b1-8fe6-f591634089e5",
                "position": {"x": 0, "y": 0},
            },
            "additionalProp2": {
                "key": "simcore/services/comp/sleeper",
                "version": "6.2.0",
                "label": "string",
                "progress": 0,
                "thumbnail": "https://string.com",
                "inputs": {},
                "inputAccess": {
                    "additionalProp1": "ReadAndWrite",
                    "additionalProp2": "ReadAndWrite",
                    "additionalProp3": "ReadAndWrite",
                },
                "inputNodes": ["ba8e4558-1088-49b1-8fe6-f591634089e5"],
                "outputs": {},
                "outputNodes": ["ba8e4558-1088-49b1-8fe6-f591634089e5"],
                "parent": "ba8e4558-1088-49b1-8fe6-f591634089e5",
                "position": {"x": 0, "y": 0},
            },
            "additionalProp3": {
                "key": "simcore/services/comp/sleeper",
                "version": "6.2.0",
                "label": "string",
                "progress": 0,
                "thumbnail": "https://string.com",
                "inputs": {},
                "inputAccess": {
                    "additionalProp1": "ReadAndWrite",
                    "additionalProp2": "ReadOnly",
                    "additionalProp3": "ReadAndWrite",
                },
                "inputNodes": [],
                "outputs": {},
                "outputNodes": [],
                "parent": None,
                "position": {"x": 0, "y": 0},
            },
        },
    }
    return deepcopy(DAG_DATA_IN_DICT)


@pytest.fixture
def minimal_app(
    monkeypatch: MonkeyPatch, mock_service_env_devel_environment: Dict[str, str]
) -> Iterator[FastAPI]:
    # disable a couple of subsystems
    monkeypatch.setenv("CATALOG_POSTGRES", "null")
    monkeypatch.setenv("CATALOG_TRACING", "null")

    app = init_app()

    # NOTE: this way we ensure the events are run in the application
    # since it starts the app on a test server
    with TestClient(app):
        yield app

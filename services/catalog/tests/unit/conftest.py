# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import sys
from copy import deepcopy
from pathlib import Path
from typing import Dict

import pytest

import simcore_service_catalog

pytest_plugins = [
    "pytest_simcore.postgres_service2",
    "pytest_simcore.schemas",
    "pytest_simcore.environs",
]

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


## FOLDER LAYOUT ------


@pytest.fixture(scope="session")
def project_slug_dir() -> Path:
    folder = current_dir.parent.parent
    assert folder.exists()
    assert any(folder.glob("src/simcore_service_catalog"))
    return folder


@pytest.fixture(scope="session")
def installed_package_dir() -> Path:
    dirpath = Path(simcore_service_catalog.__file__).resolve().parent
    assert dirpath.exists()
    return dirpath


@pytest.fixture(scope="session")
def osparc_simcore_root_dir() -> Path:
    root_dir = current_dir
    while root_dir != root_dir.parent and not any(root_dir.glob("services/catalog")):
        root_dir = root_dir.parent

    assert (
        root_dir and root_dir.exists()
    ), "Did you renamed or moved the integration folder under catalog??"
    assert any(root_dir.glob("services/catalog")), "%s not look like rootdir" % root_dir
    return root_dir


@pytest.fixture(scope="session")
def api_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "catalog"
    assert specs_dir.exists()
    return specs_dir


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
                "thumbnail": "string",
                "inputs": {},
                "inputAccess": {
                    "additionalProp1": "ReadAndWrite",
                    "additionalProp2": "ReadAndWrite",
                    "additionalProp3": "ReadAndWrite",
                },
                "inputNodes": ["string"],
                "outputs": {},
                "outputNodes": ["string"],
                "parent": "nodeUUid1",
                "position": {"x": 0, "y": 0},
            },
            "additionalProp2": {
                "key": "simcore/services/comp/sleeper",
                "version": "6.2.0",
                "label": "string",
                "progress": 0,
                "thumbnail": "string",
                "inputs": {},
                "inputAccess": {
                    "additionalProp1": "ReadAndWrite",
                    "additionalProp2": "ReadAndWrite",
                    "additionalProp3": "ReadAndWrite",
                },
                "inputNodes": ["string"],
                "outputs": {},
                "outputNodes": ["string"],
                "parent": "nodeUUid1",
                "position": {"x": 0, "y": 0},
            },
            "additionalProp3": {
                "key": "simcore/services/comp/sleeper",
                "version": "6.2.0",
                "label": "string",
                "progress": 0,
                "thumbnail": "string",
                "inputs": {},
                "inputAccess": {
                    "additionalProp1": "ReadAndWrite",
                    "additionalProp2": "ReadOnly",
                    "additionalProp3": "ReadAndWrite",
                },
                "inputNodes": ["string"],
                "outputs": {},
                "outputNodes": ["string"],
                "parent": "nodeUUid1",
                "position": {"x": 0, "y": 0},
            },
        },
    }
    return deepcopy(DAG_DATA_IN_DICT)

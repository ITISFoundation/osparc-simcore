# pylint:disable=redefined-outer-name

import json
import logging
from pathlib import Path
from typing import Dict

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def common_schemas_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "common" / "schemas"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture(scope="session")
def node_meta_schema_file(common_schemas_specs_dir: Path) -> Path:
    node_meta_file = common_schemas_specs_dir / "node-meta-v0.0.1.json"
    assert node_meta_file.exists()
    return node_meta_file


@pytest.fixture(scope="session")
def node_meta_schema(node_meta_schema_file: Path) -> Dict:
    with node_meta_schema_file.open() as fp:
        node_schema = json.load(fp)
        return node_schema

import json
from pathlib import Path
from typing import Callable, Dict

import pytest

from simcore_service_catalog.models.domain.service import ServiceData


@pytest.fixture(scope="session")
def json_diff_script(script_dir: Path) -> Path:
    json_diff_script = script_dir / "json-schema-diff.bash"
    assert json_diff_script.exists()
    return json_diff_script


@pytest.fixture(scope="session")
def diff_json_schemas(json_diff_script: Path) -> Callable:
    def diff(schema_a, schema_b) -> bool:
        return False

    yield diff


def test_generated_schema_correct(diff_json_schemas, node_meta_schema: Dict):
    generated_schema = json.loads(ServiceData.schema_json(indent=2))
    assert diff_json_schemas(node_meta_schema, generated_schema)

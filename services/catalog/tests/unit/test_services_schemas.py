# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import json
import subprocess
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
def diff_json_schemas(json_diff_script: Path, tmp_path_factory: Path) -> Callable:
    def diff(schema_a: Dict, schema_b: Dict) -> bool:
        tmp_path = tmp_path_factory.mktemp(__name__)
        schema_a_path = tmp_path / "schema_a.json"
        schema_a_path.write_text(json.dumps(schema_a))
        schema_b_path = tmp_path / "schema_b.json"
        schema_b_path.write_text(json.dumps(schema_b))
        command = f"{json_diff_script} {schema_a_path} {schema_b_path}".split(" ")
        process_completion = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=True,
            cwd=tmp_path,
        )
        assert process_completion.returncode == 0, print(
            f"Exit code {process_completion.returncode}\n{process_completion.stdout.decode('utf-8')}"
        )
        return process_completion.returncode == 0

    yield diff


def test_generated_schema_correct(diff_json_schemas: Callable, node_meta_schema: Dict):
    generated_schema = json.loads(ServiceData.schema_json(indent=2))
    assert diff_json_schemas(node_meta_schema, generated_schema)

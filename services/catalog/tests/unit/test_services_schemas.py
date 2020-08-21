# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access


import json
import subprocess
from pathlib import Path
from typing import Callable, Dict

import pytest

from simcore_service_catalog.models.domain.service import ServiceDockerData


@pytest.fixture(scope="session")
def json_diff_script(script_dir: Path) -> Path:
    json_diff_script = script_dir / "json-schema-diff.bash"
    assert json_diff_script.exists()
    return json_diff_script


@pytest.fixture(scope="session")
def diff_json_schemas(json_diff_script: Path, tmp_path_factory: Path) -> Callable:
    def _run_diff(schema_a: Dict, schema_b: Dict) -> subprocess.CompletedProcess:
        tmp_path = tmp_path_factory.mktemp(__name__)
        schema_a_path = tmp_path / "schema_a.json"
        schema_a_path.write_text(json.dumps(schema_a))
        schema_b_path = tmp_path / "schema_b.json"
        schema_b_path.write_text(json.dumps(schema_b))
        command = [json_diff_script, schema_a_path, schema_b_path]
        return subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            cwd=tmp_path,
        )

    yield _run_diff


def test_generated_schema_same_as_original(
    diff_json_schemas: Callable, node_meta_schema: Dict
):
    generated_schema = json.loads(ServiceDockerData.schema_json(indent=2))

    process_completion = diff_json_schemas(node_meta_schema, generated_schema)

    assert (
        process_completion.returncode == 0
    ), f"Exit code {process_completion.returncode}\n{process_completion.stdout.decode('utf-8')}"

    # https://www.npmjs.com/package/json-schema-diff returns true (at least in WSL whatever the result)
    # ```false``` is returned at the end of the stdout
    assert "No differences found" in process_completion.stdout.decode(
        "utf-8"
    ), process_completion.stdout.decode("utf-8")

# pylint:disable=redefined-outer-name

import json
import logging
import subprocess
from pathlib import Path
from typing import Callable, Dict

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


@pytest.fixture(scope="session")
def json_schema_dict(common_schemas_specs_dir: Path) -> Callable:
    def schema_getter(schema_name: str) -> Dict:
        json_file = common_schemas_specs_dir / schema_name
        assert (
            json_file.exists()
        ), f"Missing {schema_name} in {common_schemas_specs_dir}, please correct path"
        with json_file.open() as fp:
            return json.load(fp)

    yield schema_getter


@pytest.fixture(scope="session")
def json_faker_script(script_dir: Path) -> Path:
    json_faker_file = script_dir / "json-schema-faker.bash"
    assert json_faker_file.exists()
    return json_faker_file


@pytest.fixture(scope="session")
def random_json_from_schema(
    json_faker_script: Path, tmp_path_factory: Path
) -> Callable:
    def _generator(schema: Dict) -> Dict:
        tmp_path = tmp_path_factory.mktemp(__name__)
        schema_path = tmp_path / "schema.json"
        schema_path.write_text(schema)
        assert schema_path.exists()

        generated_json_path = tmp_path / "random_example.json"
        assert not generated_json_path.exists()

        command = [json_faker_script, schema_path, generated_json_path]
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=False,
            check=False,
            cwd=tmp_path,
        )
        assert (
            result.returncode == 0
        ), f"Issue running {result.args}, gives following errors:\n{result.stdout}"

        assert generated_json_path.exists()
        return json.loads(generated_json_path.read_text())

    yield _generator

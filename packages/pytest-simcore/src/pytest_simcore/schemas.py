# pylint:disable=redefined-outer-name

import json
import subprocess
from pathlib import Path
from typing import Any, Callable, Iterable

import pytest


@pytest.fixture(scope="session")
def common_schemas_specs_dir(osparc_simcore_root_dir: Path) -> Path:
    specs_dir = osparc_simcore_root_dir / "api" / "specs" / "director" / "schemas"
    assert specs_dir.exists()
    return specs_dir


@pytest.fixture(scope="session")
def node_meta_schema_file(common_schemas_specs_dir: Path) -> Path:
    node_meta_file = common_schemas_specs_dir / "node-meta-v0.0.1-pydantic.json"
    assert node_meta_file.exists()
    return node_meta_file


@pytest.fixture(scope="session")
def node_meta_schema(node_meta_schema_file: Path) -> dict:
    with node_meta_schema_file.open() as fp:
        node_schema = json.load(fp)
        return node_schema


@pytest.fixture(scope="session")
def json_schema_dict(common_schemas_specs_dir: Path) -> Iterable[Callable]:
    def schema_getter(schema_name: str) -> dict:
        json_file = common_schemas_specs_dir / schema_name
        assert (
            json_file.exists()
        ), f"Missing {schema_name} in {common_schemas_specs_dir}, please correct path"
        with json_file.open() as fp:
            return json.load(fp)

    yield schema_getter


@pytest.fixture(scope="session")
def json_faker_script(osparc_simcore_scripts_dir: Path) -> Path:
    json_faker_file = osparc_simcore_scripts_dir / "json-schema-faker.bash"
    assert json_faker_file.exists()
    return json_faker_file


@pytest.fixture(scope="session")
def random_json_from_schema(
    json_faker_script: Path, tmp_path_factory
) -> Iterable[Callable[[str], dict[str, Any]]]:
    # tmp_path_factory fixture: https://docs.pytest.org/en/stable/tmpdir.html

    def _generator(json_schema: str) -> dict[str, Any]:
        tmp_path = tmp_path_factory.mktemp(__name__)
        schema_path = tmp_path / "schema.json"

        schema_path.write_text(json_schema)
        assert schema_path.exists()

        print("Faking schema\n", schema_path.read_text(), "\n")

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
        ), f"Issue running {result.args}, gives following errors:\n{result.stdout.decode('utf-8')}"

        assert generated_json_path.exists()
        return json.loads(generated_json_path.read_text())

    yield _generator


@pytest.fixture(scope="session")
def json_diff_script(osparc_simcore_scripts_dir: Path) -> Path:
    json_diff_script = osparc_simcore_scripts_dir / "json-schema-diff.bash"
    assert json_diff_script.exists()
    return json_diff_script


@pytest.fixture(scope="session")
def diff_json_schemas(json_diff_script: Path, tmp_path_factory) -> Callable:
    def _run_diff(schema_lhs: dict, schema_rhs: dict) -> subprocess.CompletedProcess:
        tmpdir = tmp_path_factory.mktemp(basename=__name__, numbered=True)
        schema_lhs_path = tmpdir / "schema_lhs.json"
        schema_lhs_path.write_text(json.dumps(schema_lhs, indent=1))
        schema_rhs_path = tmpdir / "schema_rhs.json"
        schema_rhs_path.write_text(json.dumps(schema_rhs, indent=1))

        # NOTE: When debugging the differences, as of now both schemas come from
        # pydantic model, now it is possible to visually compare the difference. To do so,
        # just dereference the current pydantic schema.

        return subprocess.run(
            [json_diff_script, schema_lhs_path, schema_rhs_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            cwd=tmpdir,
        )

    return _run_diff

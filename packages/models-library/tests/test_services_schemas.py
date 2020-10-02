# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import
import json
import subprocess
import sys
from pathlib import Path
from typing import Callable, Dict

import pytest

import models_library

pytest_plugins = [
    "pytest_simcore.environs",
    "pytest_simcore.schemas",
]


@pytest.fixture(scope="session")
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


@pytest.fixture(scope="session")
def package_dir():
    pdir = Path(models_library.__file__).resolve().parent
    assert pdir.exists()
    return pdir


@pytest.fixture(scope="session")
def osparc_simcore_root_dir(here):
    root_dir = here.parent.parent.parent.resolve()
    assert root_dir.exists(), "Is this service within osparc-simcore repo?"
    assert any(root_dir.glob("packages/models-library")), (
        "%s not look like rootdir" % root_dir
    )
    return root_dir

pytest_plugins = [
    "pytest_simcore.environs",
    "pytest_simcore.schemas",
]


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

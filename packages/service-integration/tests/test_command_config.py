# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
import os
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml
from service_integration.osparc_config import OSPARC_CONFIG_DIRNAME


@pytest.fixture
def tmp_compose_spec(tests_data_dir: Path, tmp_path: Path):
    src = tests_data_dir / "docker-compose-meta.yml"
    dst = tmp_path / "docker-compose-meta.yml"
    shutil.copyfile(src, dst)
    return dst


def test_create_new_osparc_config(
    run_program_with_args: Callable, tmp_compose_spec: Path
):
    osparc_dir = tmp_compose_spec.parent / OSPARC_CONFIG_DIRNAME
    assert not osparc_dir.exists()

    result = run_program_with_args(
        "config",
        "create",
        "--from-spec-file",
        str(tmp_compose_spec),
    )
    assert result.exit_code == os.EX_OK, result.output

    assert osparc_dir.exists()

    meta_cfgs = set(osparc_dir.glob("./*/metadata.y*ml"))
    runtime_cfgs = set(osparc_dir.glob("./*/runtime.y*ml"))

    assert len(runtime_cfgs) == len(meta_cfgs)
    assert {f.parent for f in meta_cfgs} == {f.parent for f in runtime_cfgs}

    service_names = set(yaml.safe_load(tmp_compose_spec.read_text())["services"].keys())
    assert service_names == set({f.parent.name for f in meta_cfgs})

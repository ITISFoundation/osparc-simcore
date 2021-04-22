# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import os
import subprocess
from io import StringIO
from typing import Dict

from dotenv import dotenv_values

# pylint: disable=subprocess-run-check
COMMON_KWARGS = dict(
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    encoding="utf8",
)


def test_cli_help():
    completed_process = subprocess.run(
        "simcore-service-storage run --help".split(), **COMMON_KWARGS
    )

    print(completed_process.stdout)
    assert completed_process.returncode == os.EX_OK
    assert "Usage: simcore-service-storage run [OPTIONS]" in completed_process.stdout


def test_cli_printenv(
    project_env_devel_environment: None, project_env_devel_dict: Dict
):
    completed_process = subprocess.run(
        "simcore-service-storage settings --compact --verbose".split(), **COMMON_KWARGS
    )

    print(completed_process.stdout)
    assert completed_process.returncode == os.EX_OK

    stream = StringIO(completed_process.stdout)
    config = dotenv_values(stream)
    assert config

    for key, value in config.items():
        # values are in env vars or in defaults
        if key in project_env_devel_dict:
            assert project_env_devel_dict[key] == value


def test_cli_check_settings_dumps_json(project_env_devel_environment):
    completed_process = subprocess.run(
        "simcore-service-storage settings --as-json --compact".split(), **COMMON_KWARGS
    )

    print(completed_process.stdout)
    assert completed_process.returncode == os.EX_OK
    assert json.loads(completed_process.stdout), "Can load output as json"

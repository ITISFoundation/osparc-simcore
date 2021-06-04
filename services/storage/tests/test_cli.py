# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from simcore_service_storage.resources import resources

# pylint: disable=subprocess-run-check
COMMON_KWARGS = dict(
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    encoding="utf8",
)


def test_cli_help():
    completed_process = subprocess.run(
        "simcore-service-storage --help".split(), **COMMON_KWARGS
    )

    print(completed_process.stdout)
    assert completed_process.returncode == os.EX_OK
    assert "Usage: simcore-service-storage [OPTIONS]" in completed_process.stdout


def test_cli_check_settings_dumps_json(project_env_devel_environment):
    completed_process = subprocess.run(
        "simcore-service-storage --check-settings".split(), **COMMON_KWARGS
    )

    print(completed_process.stdout)
    assert completed_process.returncode == os.EX_OK
    assert json.loads(completed_process.stdout), "Can load output as json"

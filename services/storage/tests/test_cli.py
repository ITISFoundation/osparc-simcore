# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import subprocess
from simcore_service_storage.resources import resources

#pylint: disable=subprocess-run-check
COMMON_KWARGS = dict(
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    encoding="utf8",
)
import os

def test_cli_help():
    completed_process = subprocess.run(
        "simcore-service-storage --help".split(), **COMMON_KWARGS
    )

    print(completed_process.stdout)
    assert completed_process.returncode == os.EX_OK
    assert "Usage: simcore-service-storage [OPTIONS]" in completed_process.stdout


def test_cli_check_config_dumps_json(project_env_devel_environment):
    completed_process = subprocess.run(
        "simcore-service-storage --check-config".split(),
         ** COMMON_KWARGS
    )

    print(completed_process.stdout)
    assert completed_process.returncode == os.EX_OK
    assert json.loads(completed_process.stdout), "Can load output as json"


from pathlib import Path
import pytest
import sys


@pytest.mark.parametrize("config_name", resources.listdir("data"))
def test_cli_config_with_environs(config_name, project_env_devel_environment):

    config_path = Path(resources.get_path("data")) / config_name

    completed_process = subprocess.run(
        "simcore-service-storage --config".split() + [config_path], **COMMON_KWARGS
    )

    print(completed_process.stdout)
    print(completed_process.stderr, file=sys.stderr)
    assert completed_process.returncode == os.EX_OK
    config = json.loads(completed_process.stdout)

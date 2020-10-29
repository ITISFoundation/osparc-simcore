# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import subprocess


def test_cli_help():
    completed_process = subprocess.run(
        "simcore-service-storage --help".split(),
        check=True,
        stdout=subprocess.PIPE,
        encoding="utf8",
    )

    print(completed_process.stdout)
    assert "Usage: simcore-service-storage [OPTIONS]" in completed_process.stdout


def test_cli_check_config_dumps_json(project_env_devel_environment):
    completed_process = subprocess.run(
        "simcore-service-storage --check-config".split(),
        check=True,
        stdout=subprocess.PIPE,
        encoding="utf8",
    )

    print(completed_process.stdout)
    assert json.loads(completed_process.stdout), "Can load output as json"

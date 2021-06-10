# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import subprocess

from simcore_service_dask_sidecar.settings import Settings


def test_cli_start_dask_worker(mock_env_devel_environment):

    settings = Settings.create_from_envs()
    assert settings.DASK_SCHEDULER_ADDRESS

    subprocess.run(["dask-worker", "--version"], check=True)

    # subprocess.run(["dask-worker", settings.DASK_SCHEDULER_ADDRESS], check=True)


def test_start_dask_scheduler(mock_env_devel_environment):

    settings = Settings.create_from_envs()
    assert settings.DASK_SCHEDULER_ADDRESS

    subprocess.run(["dask-scheduler", "--version"], check=True)

    # subprocess.run(["dask-scheduler", settings.DASK_SCHEDULER_ADDRESS], check=True)

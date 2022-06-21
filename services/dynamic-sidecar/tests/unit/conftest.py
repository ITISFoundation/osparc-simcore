from pathlib import Path

import pytest
from fastapi import FastAPI
from pytest import MonkeyPatch
from pytest_simcore.helpers.utils_envs import EnvVarsDict, setenvs_as_envfile
from simcore_service_dynamic_sidecar.modules.mounted_fs import (
    MountedVolumes,
    setup_mounted_fs,
)


@pytest.fixture
def mounted_volumes(app: FastAPI) -> MountedVolumes:
    created_volumes: MountedVolumes = setup_mounted_fs(app)
    assert created_volumes == app.state.mounted_volumes
    return app.state.mounted_volumes


@pytest.fixture
def mock_environment_with_envdevel(
    monkeypatch: MonkeyPatch, project_slug_dir: Path
) -> EnvVarsDict:
    env_file = project_slug_dir / ".env-devel"
    envs = setenvs_as_envfile(monkeypatch, env_file.read_text())
    return envs

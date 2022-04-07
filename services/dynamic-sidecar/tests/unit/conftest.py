import pytest
from fastapi import FastAPI
from simcore_service_dynamic_sidecar.modules.mounted_fs import (
    MountedVolumes,
    setup_mounted_fs,
)


@pytest.fixture
def mounted_volumes(app: FastAPI) -> MountedVolumes:
    created_volumes: MountedVolumes = setup_mounted_fs(app)
    assert created_volumes == app.state.mounted_volumes
    return app.state.mounted_volumes

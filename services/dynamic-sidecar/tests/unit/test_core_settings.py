# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name


import uuid
from pathlib import Path, PosixPath

import pytest
from _pytest.monkeypatch import MonkeyPatch
from simcore_service_dynamic_sidecar.core.settings import (
    NonFastAPIDynamicSidecarSettings,
    get_non_fastpi_settings,
)


@pytest.fixture
def tmp_dir(tmp_path: PosixPath) -> Path:
    return Path(tmp_path)


@pytest.fixture
def mocked_non_fast_api_settings(tmp_dir: Path, monkeypatch: MonkeyPatch) -> None:
    inputs_dir = tmp_dir / "inputs"
    outputs_dir = tmp_dir / "outputs"
    monkeypatch.setenv("DY_SIDECAR_PATH_INPUTS", str(inputs_dir))
    monkeypatch.setenv("DY_SIDECAR_PATH_OUTPUTS", str(outputs_dir))
    monkeypatch.setenv("DY_SIDECAR_USER_ID", "1")
    monkeypatch.setenv("DY_SIDECAR_PROJECT_ID", f"{uuid.uuid4()}")
    monkeypatch.setenv("DY_SIDECAR_NODE_ID", f"{uuid.uuid4()}")


def test_non_fast_api_dynamic_sidecar_settings(
    mocked_non_fast_api_settings: None,
) -> None:
    assert NonFastAPIDynamicSidecarSettings()


def test_cached_settings_is_same_object(mocked_non_fast_api_settings: None) -> None:
    assert id(get_non_fastpi_settings()) == id(get_non_fastpi_settings())

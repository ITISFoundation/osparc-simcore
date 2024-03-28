import pytest
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.node_ports import StorageAuthSettings


@pytest.mark.parametrize("secure", [True, False])
def test_storage_auth_settings_secure(monkeypatch: pytest.MonkeyPatch, secure: bool):
    setenvs_from_dict(
        monkeypatch,
        {
            "STORAGE_SECURE": "1" if secure else "0",
        },
    )
    settings = StorageAuthSettings.create_from_envs()
    assert settings.base_url == f"{'https' if secure else 'http'}://storage:8080"

import pytest
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from settings_library.node_ports import StorageAuthSettings


@pytest.mark.parametrize("scheme", ["http", "https"])
def test_storage_auth_settings_secure(monkeypatch: pytest.MonkeyPatch, scheme: str):
    setenvs_from_dict(
        monkeypatch,
        {
            "STORAGE_SCHEME": scheme,
        },
    )
    settings = StorageAuthSettings.create_from_envs()
    assert settings.base_url == f"{scheme}://storage:8080"

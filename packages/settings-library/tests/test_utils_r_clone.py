import pytest
from settings_library.r_clone import RCloneSettings, S3Provider
from settings_library.utils_r_clone import _COMMON_ENTRIES, get_r_clone_config


@pytest.fixture(params=list(S3Provider))
def r_clone_settings(request, monkeypatch) -> RCloneSettings:
    monkeypatch.setenv("R_CLONE_S3_PROVIDER", request.param)
    return RCloneSettings()


def test_r_clone_config_template_replacement(r_clone_settings: RCloneSettings) -> None:
    r_clone_config = get_r_clone_config(r_clone_settings)
    print(r_clone_config)

    assert "{endpoint}" not in r_clone_config
    assert "{access_key}" not in r_clone_config
    assert "{secret_key}" not in r_clone_config

    for key in _COMMON_ENTRIES.keys():
        assert key in r_clone_config

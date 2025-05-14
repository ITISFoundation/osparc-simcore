import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    return setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,  # WARNING: AFTER env_devel_dict because HOST are set to 127.0.0.1 in here
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "WEBSERVER_FUNCTIONS": "1",
        },
    )

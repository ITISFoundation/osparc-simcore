import pytest
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict


@pytest.fixture
def enable_webserver_clusters_feature(
    app_environment: EnvVarsDict, monkeypatch: MonkeyPatch
) -> EnvVarsDict:
    monkeypatch.setenv("WEBSERVER_CLUSTERS", "1")
    return app_environment | {"WEBSERVER_CLUSTERS": "1"}

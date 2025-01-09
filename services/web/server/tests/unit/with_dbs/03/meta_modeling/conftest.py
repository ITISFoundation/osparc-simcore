# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
import pytest
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_postgres_database.models.users import UserRole


@pytest.fixture
def user_role() -> UserRole:
    return UserRole.TESTER


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            # exclude
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CLUSTERS": "null",
            "WEBSERVER_COMPUTATION": "null",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_GROUPS": "0",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_EMAIL": "null",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STORAGE": "null",
            "WEBSERVER_STUDIES_DISPATCHER": "null",
            "WEBSERVER_TAGS": "0",
            "WEBSERVER_TRACING": "null",
            # Module under test
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",
            "WEBSERVER_VERSION_CONTROL": "1",
            "WEBSERVER_META_MODELING": "1",
        },
    )

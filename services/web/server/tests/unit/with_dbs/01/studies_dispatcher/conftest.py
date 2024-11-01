# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import logging

import pytest
from pytest_mock import MockerFixture
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.log import setup_logging
from simcore_service_webserver.studies_dispatcher.settings import (
    StudiesDispatcherSettings,
)


@pytest.fixture
def app_environment(app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch):
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CATALOG": "null",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GROUPS": "1",
            "WEBSERVER_META_MODELING": "0",
            "WEBSERVER_PRODUCTS": "1",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_RABBITMQ": "null",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STORAGE": "null",
            "WEBSERVER_TAGS": "1",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_VERSION_CONTROL": "0",
            "WEBSERVER_WALLETS": "0",
        },
    )

    monkeypatch.delenv("WEBSERVER_STUDIES_DISPATCHER", raising=False)
    app_environment.pop("WEBSERVER_STUDIES_DISPATCHER", None)

    envs_studies_dispatcher = setenvs_from_dict(
        monkeypatch,
        {
            "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
            "STUDIES_GUEST_ACCOUNT_LIFETIME": "2 1:10:00",  # 2 days 1h and 10 mins
        },
    )

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    setup_logging(
        level=logging.DEBUG, log_format_local_dev_enabled=True, logger_filter_mapping={}
    )

    plugin_settings = StudiesDispatcherSettings.create_from_envs()
    print(plugin_settings.model_dump_json(indent=1))

    return {**app_environment, **envs_plugins, **envs_studies_dispatcher}


@pytest.fixture
def mock_dynamic_scheduler(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_webserver.dynamic_scheduler.api.stop_dynamic_services_in_project",
        autospec=True,
    )

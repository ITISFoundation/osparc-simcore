# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aiohttp.test_utils import make_mocked_request
from faker import Faker
from pytest import MonkeyPatch
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_envs import setenvs_from_dict
from simcore_service_webserver.application import create_application
from simcore_service_webserver.studies_dispatcher._projects_permalinks import (
    ProjectType,
    create_permalink_for_study,
)


@pytest.fixture
def app_environment(env_devel_dict: EnvVarsDict, monkeypatch: MonkeyPatch):

    # remove
    for env in ("WEBSERVER_STUDIES_DISPATCHER", "WEBSERVER_STUDIES_ACCESS_ENABLED"):
        monkeypatch.delenv(env, raising=False)
        env_devel_dict.pop(env, None)

    # override
    env_vars = setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CATALOG": "null",
            "WEBSERVER_CLUSTERS": "false",
            "WEBSERVER_COMPUTATION": "0",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_DIRECTOR": "null",
            "WEBSERVER_DIRECTOR_V2": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_GROUPS": "1",
            "WEBSERVER_META_MODELING": "null",
            "WEBSERVER_PRODUCTS": "1",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_RABBITMQ": "null",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_STORAGE": "null",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_TAGS": "1",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_USERS": "1",
            "WEBSERVER_VERSION_CONTROL": "0",
            #
            "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
        },
    )
    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    # setup_logging(level=logging.DEBUG)
    return env_vars


def test_create_permalink(
    faker: Faker,
    app_environment: EnvVarsDict,
):
    app = create_application()

    fake_request = make_mocked_request("GET", "/project", app=app)

    project_uuid = faker.uuid4()
    permalink1 = create_permalink_for_study(
        fake_request,
        project_uuid=project_uuid,
        project_type=ProjectType.TEMPLATE,
        project_access_rights={"1": {"read": True, "write": False, "delete": False}},
        project_is_public=False,
    )

    assert not permalink1.is_public
    assert permalink1.url.path.endswith(project_uuid)

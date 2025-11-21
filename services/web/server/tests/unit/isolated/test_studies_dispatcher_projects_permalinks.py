# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from faker import Faker
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.studies_dispatcher._projects_permalinks import (
    PermalinkNotAllowedError,
    ProjectType,
    create_permalink_for_study,
)
from simcore_service_webserver.studies_dispatcher.plugin import _setup_studies_access
from simcore_service_webserver.studies_dispatcher.settings import get_plugin_settings


@pytest.fixture
def app_environment(
    env_devel_dict: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # remove
    for env in ("WEBSERVER_STUDIES_DISPATCHER", "WEBSERVER_STUDIES_ACCESS_ENABLED"):
        monkeypatch.delenv(env, raising=False)
        env_devel_dict.pop(env, None)

    # override
    env_vars = setenvs_from_dict(
        monkeypatch,
        {
            **env_devel_dict,
            "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CATALOG": "null",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_DIRECTOR_V2": "null",
            "WEBSERVER_EMAIL": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_GROUPS": "1",
            "WEBSERVER_LOGIN": "null",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_PAYMENTS": "null",
            "WEBSERVER_PRODUCTS": "1",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_RABBITMQ": "null",
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_RPC_NAMESPACE": "null",
            "WEBSERVER_SCICRUNCH": "null",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STORAGE": "null",
            "WEBSERVER_TAGS": "1",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_WALLETS": "0",
        },
    )
    print(env_vars)
    return env_vars


@pytest.fixture
def app(app_environment: EnvVarsDict) -> web.Application:
    app_ = web.Application()
    setup_settings(app_)

    # minimal version of app to just add the routes
    _setup_studies_access(app_, get_plugin_settings(app_))
    return app_


@pytest.fixture
def fake_get_project_request(faker: Faker, app: web.Application) -> web.Request:
    project_uuid = faker.uuid4()
    return make_mocked_request(
        "GET",
        "https://testfoo.com/project/{project_uuid}",
        app=app,
        match_info={"project_uuid": project_uuid},
    )


@pytest.mark.parametrize("is_public", [True, False])
def test_create_permalink(fake_get_project_request: web.Request, is_public: bool):
    project_uuid: str = fake_get_project_request.match_info["project_uuid"]

    permalink = create_permalink_for_study(
        fake_get_project_request.app,
        request_url=fake_get_project_request.url,
        request_headers=dict(fake_get_project_request.headers),
        project_uuid=project_uuid,
        project_type=ProjectType.TEMPLATE,
        project_access_rights={"1": {"read": True, "write": False, "delete": False}},
        project_is_public=is_public,
    )

    assert permalink.is_public is is_public
    assert permalink.url.path.endswith(project_uuid)


@pytest.fixture(params=[True, False])
def valid_project_kwargs(
    request: pytest.FixtureRequest, fake_get_project_request: web.Request
):
    return {
        "project_uuid": fake_get_project_request.match_info["project_uuid"],
        "project_type": ProjectType.TEMPLATE,
        "project_access_rights": {"1": {"read": True, "write": False, "delete": False}},
        "project_is_public": request.param,
    }


def test_permalink_only_for_template_projects(
    fake_get_project_request: web.Request, valid_project_kwargs: dict[str, Any]
):
    with pytest.raises(PermalinkNotAllowedError):
        create_permalink_for_study(
            fake_get_project_request.app,
            request_url=fake_get_project_request.url,
            request_headers=dict(fake_get_project_request.headers),
            **{**valid_project_kwargs, "project_type": ProjectType.STANDARD}
        )


def test_permalink_only_when_read_access_to_everyone(
    fake_get_project_request: web.Request, valid_project_kwargs: dict[str, Any]
):
    with pytest.raises(PermalinkNotAllowedError):
        create_permalink_for_study(
            fake_get_project_request.app,
            request_url=fake_get_project_request.url,
            request_headers=dict(fake_get_project_request.headers),
            **{
                **valid_project_kwargs,
                "project_access_rights": {
                    "1": {"read": False, "write": False, "delete": False}
                },
            }
        )

    with pytest.raises(PermalinkNotAllowedError):
        create_permalink_for_study(
            fake_get_project_request.app,
            request_url=fake_get_project_request.url,
            request_headers=dict(fake_get_project_request.headers),
            **{
                **valid_project_kwargs,
                "project_access_rights": {
                    "2000": {"read": False, "write": False, "delete": False}
                },
            }
        )

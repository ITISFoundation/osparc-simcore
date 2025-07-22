# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import re

import pytest
from aiohttp import web_exceptions
from aioresponses.core import aioresponses
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
) -> EnvVarsDict:

    monkeypatch.delenv("WEBSERVER_STUDIES_DISPATCHER", raising=False)
    app_environment.pop("WEBSERVER_STUDIES_DISPATCHER", None)

    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            # exclude
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CATALOG": "null",
            "WEBSERVER_COMPUTATION": "null",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EMAIL": "null",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_GROUPS": "0",
            "WEBSERVER_LOGIN": "null",
            "WEBSERVER_PRODUCTS": "0",
            "WEBSERVER_PROJECTS": "null",
            "WEBSERVER_PUBLICATIONS": "0",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STORAGE": "null",
            "WEBSERVER_RESOURCE_MANAGER": "null",
            "WEBSERVER_TAGS": "0",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_USERS": "null",
        },
    )


@pytest.mark.skip(reason="UNDER DEV: test_group_handlers")
async def test_unauntheticated_request_to_scicrunch(client):

    with aioresponses() as scicrunch_service_api_mock:
        scicrunch_service_api_mock.get(
            re.compile(r"^https://scicrunch\.org/api/1/resource/fields/view/.*"),
            status=web_exceptions.HTTPUnauthorized.status_code,
        )

        with pytest.raises(web_exceptions.HTTPBadRequest):
            await client.post(
                "/v0/groups/sparc/classifiers/scicrunch-resources/SCR_018997",
                raise_for_status=True,
            )

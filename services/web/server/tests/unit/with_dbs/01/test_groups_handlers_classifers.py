# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re
from copy import deepcopy

import pytest
from aiohttp import web_exceptions
from aioresponses.core import aioresponses
from simcore_service_webserver.application_settings_utils import AppConfigDict


@pytest.fixture
def app_cfg(default_app_cfg: AppConfigDict, unused_tcp_port_factory):
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    cfg["main"]["port"] = unused_tcp_port_factory()
    cfg["main"]["studies_access_enabled"] = True

    exclude = {
        "tracing",
        "smtp",
        "storage",
        "activity",
        "diagnostics",
        "tags",
        "publications",
        "catalog",
        "computation",
        "products",
        "socketio",
        "resource_manager",
        "projects",
        "login",
        "users",
    }
    include = {
        "db",
        "rest",
        "groups",
    }

    assert include.intersection(exclude) == set()

    for section in include:
        cfg[section]["enabled"] = True
    for section in exclude:
        cfg[section]["enabled"] = False

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    ## setup_logging(level=logging.DEBUG)

    return cfg


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

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy

import pytest
from aiohttp import web
from pytest_simcore.helpers.utils_projects import create_project
from servicelib.application import create_safe_application
from simcore_service_webserver import application


@pytest.fixture
def client(loop, aiohttp_client, app_cfg, postgres_db):

    # config app
    cfg = deepcopy(app_cfg)
    port = cfg["main"]["port"]
    cfg["projects"]["enabled"] = True

    app = application.create_application(cfg)

    # server and client
    return loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": port, "host": "localhost"})
    )


@pytest.mark.skip(reason="Under dev")
def test_users_projects_db(client):
    # given schema, an easy way to produce projects?
    # a language to emulate UI??
    # See https://github.com/cwacek/python-jsonschema-objects
    #
    # api/specs/webserver/v0/components/schemas/project-v0.0.1.json
    # create_project(client.app, )
    pass


@pytest.mark.skip(reason="Under dev")
def test_cleanup_expired_guest_users(client):
    pass
    # Guests users expire

    # Shall delete all guest users and non-shared owned projects
    # that expired.

    # Shall remove all resources (data and running services) of expired users


@pytest.mark.skip(reason="Under dev -> resource management ")
def test_limit_guest_users(client):
    # a guest user has limited access to resources
    # also limited time and amount
    #
    pass

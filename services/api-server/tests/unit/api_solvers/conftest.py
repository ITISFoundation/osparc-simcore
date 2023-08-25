# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from copy import deepcopy
from typing import Any

import pytest
from fastapi import FastAPI
from pytest_simcore.helpers import faker_catalog
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture
def solver_key() -> str:
    return "simcore/services/comp/itis/sleeper"


@pytest.fixture
def solver_version() -> str:
    return "2.0.0"


@pytest.fixture
def mocked_webserver_service_api(
    app: FastAPI,
    mocked_webserver_service_api_base: MockRouter,
    patch_webserver_service_project_workflow: Callable[[MockRouter], MockRouter],
) -> MockRouter:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_WEBSERVER

    patch_webserver_service_project_workflow(mocked_webserver_service_api_base)

    return mocked_webserver_service_api_base


@pytest.fixture
def mocked_catalog_service_api(
    app: FastAPI,
    mocked_catalog_service_api_base: MockRouter,
    catalog_service_openapi_specs: dict[str, Any],
) -> MockRouter:
    respx_mock = mocked_catalog_service_api_base
    openapi = deepcopy(catalog_service_openapi_specs)
    schemas = openapi["components"]["schemas"]

    respx_mock.get(
        "/v0/services?user_id=1&details=false", name="list_services"
    ).respond(
        200,
        json=[
            # one solver
            faker_catalog.create_service_out(
                key="simcore/services/comp/Foo", name="Foo"
            ),
            # two version of the same solver
            faker_catalog.create_service_out(version="0.0.1"),
            faker_catalog.create_service_out(version="1.0.1"),
            # not a solver
            faker_catalog.create_service_out(type="dynamic"),
        ],
    )

    # -----
    # NOTE: we could use https://python-jsonschema.readthedocs.io/en/stable/
    #

    respx_mock.get(
        # NOTE: regex does not work even if tested https://regex101.com/r/drVAGr/1
        # path__regex=r"/v0/services/(?P<service_key>[\w/%]+)/(?P<service_version>[\d\.]+)/ports\?user_id=(?P<user_id>\d+)",
        path__startswith="/v0/services/simcore/services/comp/itis/sleeper/2.1.4/ports",
        name="list_service_ports",
    ).respond(
        200,
        json=[
            schemas["ServicePortGet"]["example"],
        ],
    )

    return respx_mock

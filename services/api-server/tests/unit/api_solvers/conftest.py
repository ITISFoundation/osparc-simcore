# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterator

import pytest
import respx
from fastapi import FastAPI
from pytest_simcore.helpers import catalog_data_fakers
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture(scope="session")
def catalog_service_openapi_specs(osparc_simcore_services_dir: Path) -> dict[str, Any]:

    openapi_path = osparc_simcore_services_dir / "catalog" / "openapi.json"
    openapi_specs = json.loads(openapi_path.read_text())
    return openapi_specs


@pytest.fixture
def mocked_catalog_service_api(
    app: FastAPI, catalog_service_openapi_specs: dict[str, Any]
) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_CATALOG

    openapi = deepcopy(catalog_service_openapi_specs)
    schemas = openapi["components"]["schemas"]

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_CATALOG.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        respx_mock.get("/v0/meta").respond(200, json=schemas["Meta"]["example"])

        # ----
        respx_mock.get(
            "/v0/services?user_id=1&details=false", name="list_services"
        ).respond(
            200,
            json=[
                # one solver
                catalog_data_fakers.create_service_out(
                    key="simcore/services/comp/Foo", name="Foo"
                ),
                # two version of the same solver
                catalog_data_fakers.create_service_out(version="0.0.1"),
                catalog_data_fakers.create_service_out(version="1.0.1"),
                # not a solver
                catalog_data_fakers.create_service_out(type="dynamic"),
            ],
        )

        # -----
        # NOTE: we could use https://python-jsonschema.readthedocs.io/en/stable/
        #

        respx_mock.get(
            # NOTE: regex does not work even if tested https://regex101.com/r/drVAGr/1
            # path__regex=r"/v0/services/(?P<service_key>[\w/%]+)/(?P<service_version>[\d\.]+)/ports\?user_id=(?P<user_id>\d+)",
            path__startswith="/v0/services/simcore%2Fservices%2Fcomp%2Fitis%2Fsleeper/2.1.4/ports",
            name="list_service_ports",
        ).respond(
            200,
            json=[
                schemas["ServicePortGet"]["example"],
            ],
        )

        yield respx_mock

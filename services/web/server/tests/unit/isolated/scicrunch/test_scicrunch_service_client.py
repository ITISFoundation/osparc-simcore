# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

"""
    Use this test to emulate situations with scicrunch service API

"""
import asyncio
import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from aiohttp import web
from aioresponses import aioresponses as AioResponsesMock  # noqa: N812
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.client_session import get_client_session
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.scicrunch.plugin import setup_scicrunch
from simcore_service_webserver.scicrunch.service_client import (
    ResearchResource,
    SciCrunch,
)


@pytest.fixture
def mock_scicrunch_service_api(
    fake_data_dir: Path,
    mock_env_devel_environment: EnvVarsDict,
    aioresponses_mocker: AioResponsesMock,
) -> AioResponsesMock:
    assert mock_env_devel_environment["SCICRUNCH_API_KEY"] == os.environ.get(
        "SCICRUNCH_API_KEY"
    )

    API_KEY = os.environ.get("SCICRUNCH_API_KEY")
    assert os.environ.get("SCICRUNCH_API_BASE_URL") == "https://scicrunch.org/api/1"

    # curl -X GET "https://scicrunch.org/api/1/resource/fields/autocomplete?field=Resource%20Name&value=octave" -H "accept: application/json
    aioresponses_mocker.get(
        f"https://scicrunch.org/api/1/resource/fields/autocomplete?field=Resource%20Name&value=octave&key={API_KEY}",
        status=200,
        payload={
            "data": [
                {
                    "rid": "SCR_000860",
                    "original_id": "nlx_155680",
                    "name": "cbiNifti: Matlab/Octave Nifti library",
                },
                {
                    "rid": "SCR_009637",
                    "original_id": "nlx_155924",
                    "name": "Pipeline System for Octave and Matlab",
                },
                {
                    "rid": "SCR_014398",
                    "original_id": "SCR_014398",
                    "name": "GNU Octave",
                },
            ],
            "success": "true",
        },
    )
    # curl -X GET "https://scicrunch.org/api/1/resource/fields/view/SCR_018997" -H "accept: application/json"
    aioresponses_mocker.get(
        f"https://scicrunch.org/api/1/resource/fields/view/SCR_018997?key={API_KEY}",
        status=200,
        payload=json.loads(
            (fake_data_dir / "get_osparc_resource_payload.json").read_text()
        ),
    )
    # curl -X GET "https://scicrunch.org/api/1/resource/versions/all/SCR_018997" -H "accept: application/json"
    aioresponses_mocker.get(
        f"https://scicrunch.org/api/1/resource/versions/all/SCR_018997?key={API_KEY}",
        status=200,
        payload=json.loads(
            '{"data":[{"version":2,"status":"Curated","time":1598984801,"uid":34739,"username":"Edyta Vieth","cid":null},{"version":1,"status":"Pending","time":1598898249,"uid":43,"username":"Anita Bandrowski","cid":30}],"success":true}'
        ),
    )

    return aioresponses_mocker


@pytest.fixture
async def mock_scicrunch_service_resolver(
    fake_data_dir: Path,
    mock_env_devel_environment: EnvVarsDict,
    aioresponses_mocker: AioResponsesMock,
) -> None:
    aioresponses_mocker.get(
        "https://scicrunch.org/resolver/SCR_018997.json",
        status=200,
        payload=json.loads(
            (fake_data_dir / "get_scicrunch_resolver_response.json").read_text()
        ),
    )


@pytest.fixture
def app(
    mock_env_devel_environment: EnvVarsDict,
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_server: Callable,
) -> web.Application:

    app_ = create_safe_application()

    setup_settings(app_)
    setup_scicrunch(app_)

    server = event_loop.run_until_complete(aiohttp_server(app_))
    assert server.app == app_
    return server.app


def test_setup_scicrunch_submodule(app: web.Application):
    scicrunch = SciCrunch.get_instance(app)
    assert scicrunch
    assert scicrunch.client == get_client_session(app)
    assert not get_client_session(app).closed


async def test_get_research_resource(
    app: web.Application,
    mock_scicrunch_service_resolver: None,
    mock_scicrunch_service_api: AioResponsesMock,
):
    scicrunch = SciCrunch.get_instance(app)
    resource: ResearchResource = await scicrunch.get_resource_fields(rrid="SCR_018997")

    assert resource.rrid == "RRID:SCR_018997"
    assert resource.name == "o²S²PARC"
    assert "Simulation platform" in resource.description

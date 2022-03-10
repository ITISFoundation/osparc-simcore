# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

"""
    Use this test to emulate situations with scicrunch service API

"""
import json
import os
from pathlib import Path

import pytest
from aioresponses.core import aioresponses
from servicelib.aiohttp.application import create_safe_application
from servicelib.aiohttp.client_session import get_client_session
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.scicrunch.plugin import setup_scicrunch
from simcore_service_webserver.scicrunch.service_client import (
    ResearchResource,
    SciCrunch,
)


@pytest.fixture
async def mock_scicrunch_service_api(fake_data_dir: Path, mock_env_devel_environment):
    assert mock_env_devel_environment["SCICRUNCH_API_KEY"] == os.environ.get(
        "SCICRUNCH_API_KEY"
    )

    API_KEY = os.environ.get("SCICRUNCH_API_KEY")
    assert os.environ.get("SCICRUNCH_API_BASE_URL") == "https://scicrunch.org/api/1"

    with aioresponses() as mock:
        # curl -X GET "https://scicrunch.org/api/1/resource/fields/autocomplete?field=Resource%20Name&value=octave" -H "accept: application/json
        mock.get(
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
        mock.get(
            f"https://scicrunch.org/api/1/resource/fields/view/SCR_018997?key={API_KEY}",
            status=200,
            payload=json.loads(
                (fake_data_dir / "get_osparc_resource_payload.json").read_text()
            ),
        )
        # curl -X GET "https://scicrunch.org/api/1/resource/versions/all/SCR_018997" -H "accept: application/json"
        mock.get(
            f"https://scicrunch.org/api/1/resource/versions/all/SCR_018997?key={API_KEY}",
            status=200,
            payload=json.loads(
                '{"data":[{"version":2,"status":"Curated","time":1598984801,"uid":34739,"username":"Edyta Vieth","cid":null},{"version":1,"status":"Pending","time":1598898249,"uid":43,"username":"Anita Bandrowski","cid":30}],"success":true}'
            ),
        )

        yield mock


@pytest.fixture
async def mock_scicrunch_service_resolver(
    fake_data_dir: Path, mock_env_devel_environment, aioresponses_mocker
):
    aioresponses_mocker.get(
        "https://scicrunch.org/resolver/SCR_018997.json",
        status=200,
        payload=json.loads(
            (fake_data_dir / "get_scicrunch_resolver_response.json").read_text()
        ),
    )


@pytest.fixture
async def fake_app(mock_env_devel_environment):
    # By using .env-devel we ensure all needed variables are at
    # least defined there
    print("app's environment variables", format(mock_env_devel_environment))

    app = create_safe_application()

    setup_settings(app)
    setup_scicrunch(app)

    yield app

    client = get_client_session(app)
    await client.close()


## TESTS -------------------------------------------------------


def test_setup_scicrunch_submodule(fake_app):
    # scicruch should be init
    scicrunch = SciCrunch.get_instance(fake_app)
    assert scicrunch
    assert scicrunch.client == get_client_session(fake_app)


async def test_get_research_resource(fake_app, mock_scicrunch_service_resolver):
    # mock_scicrunch_service_api):
    scicrunch = SciCrunch.get_instance(fake_app)
    resource: ResearchResource = await scicrunch.get_resource_fields(rrid="SCR_018997")

    assert resource.rrid == "RRID:SCR_018997"
    assert resource.name == "o²S²PARC"
    assert "Simulation platform" in resource.description

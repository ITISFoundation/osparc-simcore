# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
import os
from pathlib import Path
from pprint import pprint

import pytest
from aioresponses.core import aioresponses
from servicelib.client_session import get_client_session
from simcore_service_webserver.scicrunch.service_client import ValidationResult
from simcore_service_webserver.scicrunch.submodule_setup import (
    SciCrunchAPI,
    setup_scicrunch_submodule,
)

# From https://scicrunch.org/resources
VALID_RRID_SAMPLES = [
    ("Antibody", "RRID:AB_90755"),
    ("Plasmid", "RRID:Addgene_44362"),
    ("Organism", "RRID:MMRRC_026409-UCD"),
    ("Cell Line", "RRID:CVCL_0033"),
    ("Tool", "RRID:SCR_007358"),
]


@pytest.fixture(scope="session")
async def mock_scicrunch_service_api(fake_data_dir: Path, mock_env_devel_environment):
    assert mock_env_devel_environment["SCICRUNCH_API_SECRET"] == os.environ.get(
        "SCICRUNCH_API_SECRET"
    )

    API_KEY = os.environ.get("SCICRUNCH_API_SECRET")
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
                """
                {
                    "data": [
                        {
                            "version": 2,
                            "status": "Curated",
                            "time": 1598984801,
                            "uid": 34739,
                            "username": "Edyta Vieth",
                            "cid": null,
                        },
                        {
                            "version": 1,
                            "status": "Pending",
                            "time": 1598898249,
                            "uid": 43,
                            "username": "Anita Bandrowski",
                            "cid": 30,
                        },
                    ],
                    "success": true,
                }
                """
            ),
        )

        yield mock


@pytest.fixture
async def fake_app(mock_env_devel_environment, loop):
    # By using .env-devel we ensure all needed variables are at
    # least defined there
    pprint("app's environment variables", mock_env_devel_environment)

    app = {}
    client = get_client_session(app)

    yield app
    await client.close()


@pytest.fixture
async def scicrunch(fake_app):
    setup_scicrunch_submodule(fake_app)
    return SciCrunchAPI.get_instance(fake_app, raises=True)


## TESTS -------------------------------------------------------

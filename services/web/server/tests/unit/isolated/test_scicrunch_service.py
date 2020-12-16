"""
    Tests actual scicrunch service

    NOTE: this is intended for manual testing during development
    NOTE: must define a valid RRID_PORTAL_API_KEY
"""

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import os
from pprint import pprint

import pytest
from aiohttp import ClientSession
from servicelib.client_session import get_client_session
from simcore_service_webserver.scicrunch import SciCrunchAPI, SciCrunchSettings
from simcore_service_webserver.scicrunch_api import ValidationResult
from simcore_service_webserver.scicrunch_models import ListOfResourceHits

SCICRUNCH_API_KEY = os.environ.get("SCICRUNCH_API_KEY")

pytestmark = pytest.mark.skipif(
    SCICRUNCH_API_KEY is None or "replace me" in SCICRUNCH_API_KEY.lower(),
    reason="Testing against actual service is intended for manual exploratory testing ONLY",
)


@pytest.fixture
async def fake_app(monkeypatch, loop):
    # setup
    app = {}
    client = get_client_session(app)
    yield app
    # tear-down
    await client.close()


@pytest.fixture
async def scicrunch(fake_app) -> SciCrunchAPI:
    scicrunch_api = SciCrunchAPI.acquire_instance(
        app=fake_app, settings=SciCrunchSettings(api_key=SCICRUNCH_API_KEY)
    )
    assert scicrunch_api is SciCrunchAPI.get_instance(fake_app)
    return scicrunch_api


# From https://scicrunch.org/resources
VALID_RRID_SAMPLES = [
    ("Antibody", "RRID:AB_90755"),
    ("Plasmid", "RRID:Addgene_44362"),
    ("Organism", "RRID:MMRRC_026409-UCD"),
    ("Cell Line", "RRID:CVCL_0033"),
    ("Tool", "RRID:SCR_007358"),
]


async def test_scicrunch_service_api_specs(loop):
    async with ClientSession() as client:
        resp = await client.get("https://scicrunch.org/swagger-docs/swagger.json")
        openapi_specs = await resp.json()
        pprint(openapi_specs["info"])
        assert openapi_specs["info"]["version"] == 1


@pytest.mark.parametrize(
    "name,rrid",
    [
        ("Jupyter Notebook", "SCR_018315"),
        ("Language::Python", "SCR_008394"),
        ("Language::Octave", "SCR_014398"),
        ("osparc", "SCR_018997"),  # proper citation: (o²S²PARC, RRID:SCR_018997)
        ("Octave", "RRID:SCR_014398"),  # TODO: should be valid!
        (None, "SCR_INVALID_XXXXX"),
        (None, "ANOTHER_INVALID_RRID"),
    ]
    + VALID_RRID_SAMPLES,
)
async def test_scicrunch_service_rrid_validation(name, rrid, scicrunch):

    validation_result = await scicrunch.validate_rrid(rrid)

    assert validation_result == (
        ValidationResult.VALID if name else ValidationResult.INVALID
    ), f"{name} with rrid={rrid} is undefined"


@pytest.mark.parametrize(
    "name,rrid",
    [
        ("Jupyter Notebook", "SCR_018315"),
        ("Language::Python", "SCR_008394"),
        ("Language::Octave", "SCR_014398"),
        ("osparc", "SCR_018997"),  # proper citation: (o²S²PARC, RRID:SCR_018997)
    ]
    + VALID_RRID_SAMPLES,
)
async def test_scicrunch_service_get_rrid_fields(name, rrid, scicrunch):
    assert name is not None
    resource = await scicrunch.get_resource_fields(rrid)
    assert resource.scicrunch_id == rrid


async def test_scicrunch_service_autocomplete(scicrunch):

    expected = ListOfResourceHits(
        __root__=[
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
            {"rid": "SCR_014398", "original_id": "SCR_014398", "name": "GNU Octave"},
        ]
    )

    hits = await scicrunch.search_resource("octave")
    assert expected == hits

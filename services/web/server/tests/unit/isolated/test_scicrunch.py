# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import os
from pprint import pprint

import pytest
from aiohttp import ClientSession
from servicelib.client_session import get_client_session
from simcore_service_webserver.scicrunch import (
    SciCrunchAPI,
    SciCrunchSettings,
    ValidationResult,
)

# TODO: emulate server for testing
RRID_PORTAL_API_KEY = os.environ.get("RRID_PORTAL_API_KEY")


@pytest.fixture
async def fake_app(monkeypatch, loop):
    app = {}
    client = get_client_session(app)

    yield app
    await client.close()


@pytest.fixture
async def scicrunch(fake_app):
    scicrunch_api = SciCrunchAPI.create_instance(
        app=fake_app, settings=SciCrunchSettings(api_key=RRID_PORTAL_API_KEY)
    )
    assert scicrunch_api is SciCrunchAPI.get_instance(fake_app)
    return scicrunch_api


@pytest.mark.skipif(
    RRID_PORTAL_API_KEY is None,
    reason="Testing agains actual service is intended for manual exploratory testing",
)
async def test_scicrunch_api_specs(loop):
    async with ClientSession() as client:
        resp = await client.get("https://scicrunch.org/swagger-docs/swagger.json")
        openapi_specs = await resp.json()
        pprint(openapi_specs["info"])
        assert openapi_specs["info"]["version"] == 1


@pytest.mark.skipif(
    RRID_PORTAL_API_KEY is None,
    reason="Testing agains actual service is intended for manual exploratory testing",
)
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
    ],
)
async def test_rrid_validation(name, rrid, scicrunch):

    validation_result = await scicrunch.validate_rrid(rrid)

    assert validation_result == (
        ValidationResult.VALID if name else ValidationResult.INVALID
    ), f"{name} with rrid={rrid} is undefined"


@pytest.mark.skipif(
    RRID_PORTAL_API_KEY is None,
    reason="Testing agains actual service is intended for manual exploratory testing",
)
@pytest.mark.parametrize(
    "name,rrid",
    [
        ("Jupyter Notebook", "SCR_018315"),
        ("Language::Python", "SCR_008394"),
        ("Language::Octave", "SCR_014398"),
        ("osparc", "SCR_018997"),  # proper citation: (o²S²PARC, RRID:SCR_018997)
    ],
)
async def test_get_rrid_fields(name, rrid, scicrunch):
    resource = await scicrunch.get_resource_fields(rrid)
    assert resource.scicrunch_id == rrid

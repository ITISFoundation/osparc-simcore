# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

"""
    Tests raw communication with scicrunch service API

    - Use for systematic exploration of the API
    - Analyzes responses of the API to known situtations
    - Ensures parts of the scicrunch service API that we use do not change interface or behaviour

    NOTE: this is intended for manual testing during development
    NOTE: skipped if it does not define a valid SCICRUNCH_API_KEY
"""

import os
from pprint import pprint
from typing import Any

import pytest
from aiohttp import ClientResponseError, ClientSession
from pytest_simcore.helpers.scrunch_citations import NOT_TOOL_CITATIONS, TOOL_CITATIONS
from servicelib.aiohttp import status
from simcore_service_webserver.scicrunch._rest import (
    ListOfResourceHits,
    ResourceView,
    autocomplete_by_name,
    get_all_versions,
    get_resource_fields,
)
from simcore_service_webserver.scicrunch.settings import (
    SCICRUNCH_DEFAULT_URL,
    SciCrunchSettings,
)

SCICRUNCH_API_KEY = os.environ.get("SCICRUNCH_API_KEY")

pytestmark = pytest.mark.skipif(
    SCICRUNCH_API_KEY is None or "REPLACE ME" in SCICRUNCH_API_KEY.upper(),
    reason=(
        "Testing against actual service is intended for manual exploratory testing ONLY."
        " Set environment valid SCICRUNCH_API_KEY to reactivate"
    ),
)


async def test_scicrunch_openapi_specs(settings: SciCrunchSettings):
    async with ClientSession() as client:
        resp = await client.get(f"{SCICRUNCH_DEFAULT_URL}/swagger-docs/swagger.json")
        openapi_specs = await resp.json()
        pprint(openapi_specs["info"])

        expected_api_version = 1
        assert openapi_specs["info"]["version"] == expected_api_version

        assert (
            str(settings.SCICRUNCH_API_BASE_URL)
            == f"{SCICRUNCH_DEFAULT_URL}/api/{expected_api_version}"
        )


@pytest.mark.parametrize("name,rrid", TOOL_CITATIONS)
async def test_scicrunch_get_all_versions(
    name: str | None, rrid: str, settings: SciCrunchSettings
):
    async with ClientSession() as client:
        versions = await get_all_versions(rrid, client, settings)
        pprint(versions)

        assert versions


@pytest.mark.parametrize(
    "rrid",
    [
        "SCR_INVALID_XXXXX",
        "ANOTHER_INVALID_RRID",
        "RRID:SCR_007358",  # valid RRID with  WITH prefix!
        # any other thing that is NOT a TOOL
    ]
    + [c[-1] for c in NOT_TOOL_CITATIONS],
)
async def test_scicrunch_get_all_versions_with_invalid_rrids(
    rrid: str, settings: SciCrunchSettings
):
    async with ClientSession() as client:
        versions = await get_all_versions(rrid, client, settings)
        pprint(versions)

        # invalid keys return success but an empty list of versions!
        assert isinstance(versions, list)
        assert len(versions) == 0
        assert not versions


async def test_scicrunch_get_all_versions_with_empty(settings: SciCrunchSettings):
    rrid = ""
    async with ClientSession() as client:
        with pytest.raises(ClientResponseError) as exc_info:
            await get_all_versions(rrid, client, settings)

        assert exc_info.value.status == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("name,rrid", TOOL_CITATIONS)
async def test_scicrunch_get_resource_fields(
    name: str | None, rrid: str, settings: SciCrunchSettings
):
    async with ClientSession() as client:
        resource_view: ResourceView = await get_resource_fields(rrid, client, settings)

        assert rrid in resource_view.scicrunch_id
        assert resource_view.get_name() == name
        assert resource_view.get_description()
        assert resource_view.get_resource_url()


@pytest.mark.parametrize(
    "rrid",
    [
        "",
        "SCR_INVALID_XXXXX",
        "ANOTHER_INVALID_RRID",
        "RRID:SCR_008394",  # has RRID: prefix
        "Addgene_44362",  # not SCR source
    ]
    + [c[-1] for c in NOT_TOOL_CITATIONS],
)
async def test_scicrunch_get_fields_from_invalid_rrid(
    rrid: str, settings: SciCrunchSettings
):
    # - ONLY RRIDs from SCR sources are actually supported
    # - 'RRID:' prefix should NOT be used here!
    expected_status_code = status.HTTP_400_BAD_REQUEST

    if rrid == "":
        expected_status_code = status.HTTP_404_NOT_FOUND

    async with ClientSession() as client:
        with pytest.raises(ClientResponseError) as exc_info:
            await get_resource_fields(rrid, client, settings)

        assert exc_info.value.status == expected_status_code


async def test_scicrunch_service_autocomplete_by_name(settings: SciCrunchSettings):

    expected: list[dict[str, Any]] = ListOfResourceHits.model_validate(
        [
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
    ).model_dump()["root"]

    async with ClientSession() as client:

        for guess_name in ("octave", "Octave", "octave  "):

            resource_hits = await autocomplete_by_name("octave", client, settings)

            hits = resource_hits.model_dump()["root"]

            assert expected == hits, f"for {guess_name}"

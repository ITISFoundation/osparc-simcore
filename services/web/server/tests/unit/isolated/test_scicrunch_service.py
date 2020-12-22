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
import re
from pprint import pprint
from typing import Any, Dict, List, Optional, Tuple

import pytest
from aiohttp import ClientResponseError, ClientSession, web
from simcore_service_webserver.scicrunch._config import SCICRUNCH_DEFAULT_URL
from simcore_service_webserver.scicrunch.scicrunch_models import (
    ListOfResourceHits,
    ResourceView,
)
from simcore_service_webserver.scicrunch.service_client import (
    autocomplete_by_name,
    get_all_versions,
    get_resource_fields,
)
from simcore_service_webserver.scicrunch.submodule_setup import SciCrunchSettings

SCICRUNCH_API_KEY = os.environ.get("SCICRUNCH_API_KEY")

pytestmark = pytest.mark.skipif(
    SCICRUNCH_API_KEY is None or "REPLACE ME" in SCICRUNCH_API_KEY.upper(),
    reason=(
        "Testing against actual service is intended for manual exploratory testing ONLY."
        " Set environment valid SCICRUNCH_API_KEY to reactivate"
    ),
)

# Citations according to https://scicrunch.org/resources -------------------


def split_citations(citations: List[str]) -> List[Tuple[str, str]]:
    def _split(citation: str) -> Tuple[str, str]:
        if "," not in citation:
            citation = citation.replace("(", "(,")
        name, rrid = re.match(r"^\((.*),\s*RRID:(.+)\)$", citation).groups()
        return name, rrid

    return list(map(_split, citations))


# http://antibodyregistry.org/AB_90755
ANTIBODY_CITATIONS = split_citations(["(Millipore Cat# AB1542, RRID:AB_90755)"])

# https://www.addgene.org/44362/
PLAMID_CITATIONS = split_citations(["(RRID:Addgene_44362)"])

#  MMRRC, catalog https://www.mmrrc.org/catalog/cellLineSDS.php?mmrrc_id=26409
ORGANISM_CITATIONS = split_citations(["(MMRRC Cat# 026409-UCD, RRID:MMRRC_026409-UCD)"])

# https://web.expasy.org/cellosaurus/CVCL_0033
CELL_LINE_CITATIONS = split_citations(["(NCBI_Iran Cat# C207, RRID:CVCL_0033)"])

# https://scicrunch.org/resources/Tools/search?q=SCR_018315&l=SCR_018315
TOOL_CITATIONS = split_citations(
    [
        "(CellProfiler Image Analysis Software, RRID:SCR_007358)",
        "(Jupyter Notebook, RRID:SCR_018315)",
        "(Python Programming Language, RRID:SCR_008394)",
        "(GNU Octave, RRID:SCR_014398)",
        "(o²S²PARC, RRID:SCR_018997)",
    ]
)


NOT_TOOL_CITATIONS = (
    ANTIBODY_CITATIONS + PLAMID_CITATIONS + ORGANISM_CITATIONS + CELL_LINE_CITATIONS
)


@pytest.fixture
async def settings(loop) -> SciCrunchSettings:
    return SciCrunchSettings(api_key=SCICRUNCH_API_KEY)


async def test_scicrunch_openapi_specs(settings: SciCrunchSettings):
    async with ClientSession() as client:
        resp = await client.get(f"{SCICRUNCH_DEFAULT_URL}/swagger-docs/swagger.json")
        openapi_specs = await resp.json()
        pprint(openapi_specs["info"])

        expected_api_version = 1
        assert openapi_specs["info"]["version"] == expected_api_version

        assert (
            str(settings.api_base_url)
            == f"{SCICRUNCH_DEFAULT_URL}/api/{expected_api_version}"
        )


@pytest.mark.parametrize("name,rrid", TOOL_CITATIONS)
async def test_scicrunch_get_all_versions(
    name: Optional[str], rrid: str, settings: SciCrunchSettings
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
        assert isinstance(versions, List)
        assert len(versions) == 0
        assert not versions


async def test_scicrunch_get_all_versions_with_empty(settings: SciCrunchSettings):
    rrid = ""
    async with ClientSession() as client:
        with pytest.raises(ClientResponseError) as exc_info:
            await get_all_versions(rrid, client, settings)

        assert exc_info.value.status == web.HTTPNotFound.status_code


@pytest.mark.parametrize("name,rrid", TOOL_CITATIONS)
async def test_scicrunch_get_resource_fields(
    name: Optional[str], rrid: str, settings: SciCrunchSettings
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
    expected_status_code = web.HTTPBadRequest.status_code

    if rrid == "":
        expected_status_code = web.HTTPNotFound.status_code

    async with ClientSession() as client:
        with pytest.raises(ClientResponseError) as exc_info:
            await get_resource_fields(rrid, client, settings)

        assert exc_info.value.status == expected_status_code


async def test_scicrunch_service_autocomplete_by_name(settings: SciCrunchSettings):

    expected: List[Dict[str, Any]] = ListOfResourceHits.parse_obj(
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
    ).dict()["__root__"]

    async with ClientSession() as client:

        for guess_name in ("octave", "Octave", "octave  "):

            resource_hits = await autocomplete_by_name("octave", client, settings)

            hits = resource_hits.dict()["__root__"]

            assert expected == hits, f"for {guess_name}"

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aiohttp import ClientSession
from aiohttp.client import ClientTimeout

# FIXME: PC check the CELL_LINE_CITATIONS test please
from pytest_simcore.helpers.utils_scrunch_citations import (  # CELL_LINE_CITATIONS,
    ANTIBODY_CITATIONS,
    ORGANISM_CITATIONS,
    PLAMID_CITATIONS,
    TOOL_CITATIONS,
)
from simcore_service_webserver.scicrunch._resolver import ResolvedItem, resolve_rrid
from simcore_service_webserver.scicrunch.settings import SciCrunchSettings


@pytest.mark.parametrize(
    "name,rrid",
    TOOL_CITATIONS + ANTIBODY_CITATIONS + PLAMID_CITATIONS + ORGANISM_CITATIONS
    # + CELL_LINE_CITATIONS, PC: this one fails
)
async def test_scicrunch_resolves_all_valid_rrids(
    name: str, rrid: str, settings: SciCrunchSettings
):
    # NOTE: this test run against https://scicrunch.org/resolver/{SCR_018997}.json
    # which is an open API (no auth required). Any change in the responses of that
    # service might cause a failure on this test
    # This tests checks some of the structure "deduced" from the responses so far.

    async with ClientSession(timeout=ClientTimeout(total=30)) as client:
        resolved = await resolve_rrid(identifier=rrid, client=client, settings=settings)

        assert resolved
        assert isinstance(resolved, ResolvedItem)

        if resolved.is_unique and name:
            assert name in resolved.proper_citation

        assert rrid in resolved.proper_citation

        # NOTE: proper_citation does not seem to have a standard format.
        # So far I found four different formats!! :-o
        if not name:
            # only rrid with a prefix
            assert resolved.proper_citation == f"RRID:{rrid}"
        else:
            # proper_citation includes both 'name' and 'rrid' but in different formats!

            #
            # NOTE: why CELL_LINE_CITATIONS are removed from test parametrization ?
            #   Since Sep.2021, test is not repeatable since the list order returned by
            #   https://scicrunch.org/resolver/RRID:CVCL_0033.json changes per call and
            #   sometimes (BCRJ Cat# 0226, RRID:CVCL_0033) appears as first hit instead
            #   of the reference in CELL_LINE_CITATIONS
            #

            assert resolved.proper_citation in (
                f"({name}, RRID:{rrid})",
                f"({name},RRID:{rrid})",
                f"{name} (RRID:{rrid})",
            )

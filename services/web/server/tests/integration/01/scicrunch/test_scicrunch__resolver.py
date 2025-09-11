# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aiohttp import ClientSession
from aiohttp.client import ClientTimeout
from pytest_simcore.helpers.scrunch_citations import (
    ANTIBODY_CITATIONS,
    ORGANISM_CITATIONS,
    PLAMID_CITATIONS,
    TOOL_CITATIONS,
)
from simcore_service_webserver.scicrunch._resolver import ResolvedItem, resolve_rrid
from simcore_service_webserver.scicrunch.settings import SciCrunchSettings


@pytest.mark.skip(
    "requires a fix see case https://github.com/ITISFoundation/osparc-simcore/issues/5160"
)
@pytest.mark.parametrize(
    "name,rrid",
    TOOL_CITATIONS + ANTIBODY_CITATIONS + PLAMID_CITATIONS + ORGANISM_CITATIONS,
)
async def test_scicrunch_resolves_all_valid_rrids(
    name: str, rrid: str, settings: SciCrunchSettings
):
    # NOTE: this test run against https://scicrunch.org/resolver/{SCR_018997}.json
    # which is an open API (no auth required). Any change in the responses of that
    # service might cause a failure on this test
    # This tests checks some of the structure "deduced" from the responses so far.
    # - Old problems: https://github.com/ITISFoundation/osparc-simcore/issues/3043

    async with ClientSession(timeout=ClientTimeout(total=30)) as client:
        resolved_items: list[ResolvedItem] = await resolve_rrid(
            identifier=rrid, client=client, settings=settings
        )

        for resolved in resolved_items:
            assert resolved
            assert isinstance(resolved, ResolvedItem)

            if resolved.is_unique and name:
                assert name in resolved.proper_citation

            assert rrid in resolved.proper_citation

        # NOTE: proper_citation does not seem to have a standard format.
        # So far I found four different formats!! :-o
        if not name:
            # only rrid with a prefix
            assert any(
                resolved.proper_citation == f"RRID:{rrid}"
                for resolved in resolved_items
            )
        else:
            # proper_citation includes both 'name' and 'rrid' but in different formats!

            #
            # NOTE: why CELL_LINE_CITATIONS are removed from test parametrization ?
            #   Since Sep.2021, test is not repeatable since the list order returned by
            #   https://scicrunch.org/resolver/RRID:CVCL_0033.json changes per call and
            #   sometimes (BCRJ Cat# 0226, RRID:CVCL_0033) appears as first hit instead
            #   of the reference in CELL_LINE_CITATIONS
            #

            assert any(
                resolved.proper_citation
                in (
                    f"({name}, RRID:{rrid})",
                    f"({name},RRID:{rrid})",
                    f"{name} (RRID:{rrid})",
                )
                for resolved in resolved_items
            )

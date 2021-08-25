# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aiohttp import ClientSession
from simcore_service_webserver.scicrunch._resolver import ResolvedItem, resolve_rrid
from simcore_service_webserver.scicrunch.submodule_setup import SciCrunchSettings

from ._citations import (
    ANTIBODY_CITATIONS,
    CELL_LINE_CITATIONS,
    ORGANISM_CITATIONS,
    PLAMID_CITATIONS,
    TOOL_CITATIONS,
)


@pytest.mark.parametrize(
    "name,rrid",
    TOOL_CITATIONS
    + ANTIBODY_CITATIONS
    + PLAMID_CITATIONS
    + ORGANISM_CITATIONS
    + CELL_LINE_CITATIONS,
)
async def test_scicrunch_resolves_all_valid_rrids(
    name: str, rrid: str, settings: SciCrunchSettings
):
    async with ClientSession() as client:
        resolved = await resolve_rrid(rrid, client, settings)

        assert resolved
        assert isinstance(resolved, ResolvedItem)

        if resolved.is_unique:
            assert name in resolved.proper_citation

        assert rrid in resolved.proper_citation
        # assert resolved.proper_citation == (f"({name}, RRID:{rrid})" if name else rrid)
        # assert resolved.proper_citation == (f"{name} (RRID:{rrid})" if name else rrid)

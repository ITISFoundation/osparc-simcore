# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import re

import pytest
from simcore_service_webserver.scicrunch.models import (
    STRICT_RRID_PATTERN,
    ResearchResource,
    normalize_rrid_tags,
)

# Cite as  (Python Programming Language, RRID:SCR_008394)
RRID_CITATIONS = [
    # From https://scicrunch.org/resources
    ("Antibody", "RRID:AB_90755"),
    ("Plasmid", "RRID:Addgene_44362"),
    ("Organism", "RRID:MMRRC_026409-UCD"),
    ("Cell Line", "RRID:CVCL_0033"),
    ("Tool", "RRID:SCR_007358"),
    # From https://scicrunch.org/resources/Any/search?q=python&l=python
    ("", "RRID:Addgene_46345"),
    ("CVXOPT - Python Software for Convex Optimization", "RRID:SCR_002918"),
    ("Python Programming Language", "RRID:SCR_008394"),
]


@pytest.mark.parametrize(
    "rrid_tag",
    [c[-1] for c in RRID_CITATIONS] + [" RRID:   SCR_008394   ", "SCR_008394"],
)
def test_normalize_rrid_tags(rrid_tag):
    rrid_tag_normalized = normalize_rrid_tags(rrid_tag)

    match = re.match(STRICT_RRID_PATTERN, rrid_tag_normalized)
    assert match is not None, f"could not identify {rrid_tag}"

    prefix, source_authority, identifier = (
        match.group(1),
        match.group(2),
        match.group(3),
    )

    assert prefix == "RRID:"
    assert source_authority in (
        "AB",  # Antibody Registry
        "CVCL",  # Cellosaurus
        "MMRRC",  # Mutant Mouse Regional Resource Centers
        "SCR",  # SciCrunch registry of tools
        "Addgene",
    )  # So far, we now these ... extend if necessary
    assert identifier

    if source_authority == "SCR":
        assert int(identifier) > 0


@pytest.mark.parametrize("name, rrid_tag", RRID_CITATIONS)
def test_research_resource_model(name, rrid_tag):

    resource = ResearchResource(
        rrid=rrid_tag, name=name, description="Something about {name}"
    )

    assert re.match(STRICT_RRID_PATTERN, resource.rrid)

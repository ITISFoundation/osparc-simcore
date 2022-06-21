# Citations according to https://scicrunch.org/resources
"""
    NOTES:

    - scicrunch API ONLY recognizes RRIDs from SciCrunch registry of tools (i.e. with prefix "SCR")
    - scicrunch web search handles ALL RRIDs (see below example of citations from other)
    - scicrunch API does NOT uses 'RRID:' prefix in rrid request parameters

"""

import re


def split_citations(citations: list[str]) -> list[tuple[str, str]]:
    def _split(citation: str) -> tuple[str, str]:
        if "," not in citation:
            citation = citation.replace("(", "(,")
        name, rrid = re.match(r"^\((.*),\s*RRID:(.+)\)$", citation).groups()
        return name, rrid

    return list(map(_split, citations))


# http://antibodyregistry.org/AB_90755
ANTIBODY_CITATIONS = split_citations(["(Millipore Cat# AB1542, RRID:AB_90755)"])

# https://www.addgene.org/44362/
PLAMID_CITATIONS = split_citations(["(RRID:Addgene_44362)"])

#  MMRRC,
# catalog https://www.mmrrc.org/catalog/cellLineSDS.php?mmrrc_id=26409
#         https://scicrunch.org/resolver/RRID:MMRRC_026409-UCD.json
#
# As of May 2022, changed proper_citation change from
#  '(MMRRC Cat# 026409-UCD, RRID:MMRRC_026409-UCD)' to
#  'RRID:MMRRC_026409-UCD'
#
ORGANISM_CITATIONS = split_citations(["(RRID:MMRRC_026409-UCD)"])

# https://web.expasy.org/cellosaurus/CVCL_0033
# As of May 2022, name changed from 'ATCC Cat# HTB-30' to 'AddexBio Cat# C0006007/65'
CELL_LINE_CITATIONS = split_citations(["(AddexBio Cat# C0006007/65, RRID:CVCL_0033)"])

#
#  WARNING: Since Sep.2021, the order of the resolved hits list returned by
#  https://scicrunch.org/resolver/RRID:CVCL_0033.json changes per call and
#  sometimes (BCRJ Cat# 0226, RRID:CVCL_0033) appears as first hit instead

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

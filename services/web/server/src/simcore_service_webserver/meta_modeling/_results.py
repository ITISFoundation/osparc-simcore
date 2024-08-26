""" Access to the to projects module

    - Adds a middleware to intercept /projects/* requests
    - Implements a MetaProjectRunPolicy policy (see director_v2_abc.py) to define how meta-projects run

"""


import logging
from typing import Any

from models_library.projects_nodes import OutputsDict
from models_library.projects_nodes_io import NodeIDStr
from pydantic import BaseModel, ConstrainedInt, Field

_logger = logging.getLogger(__name__)


class ProgressInt(ConstrainedInt):
    ge = 0
    le = 100


class ExtractedResults(BaseModel):
    progress: dict[NodeIDStr, ProgressInt] = Field(
        ..., description="Progress in each computational node"
    )
    labels: dict[NodeIDStr, str] = Field(
        ..., description="Maps captured node with a label"
    )
    values: dict[NodeIDStr, OutputsDict] = Field(
        ..., description="Captured outputs per node"
    )

    class Config:
        schema_extra = {
            "example": {
                # sample with 2 computational services, 2 data sources (iterator+parameter) and 2 observers (probes)
                "progress": {
                    "4c08265a-427b-4ac3-9eab-1d11c822ada4": 0,
                    "e33c6880-1b1d-4419-82d7-270197738aa9": 100,
                },
                "labels": {
                    "0f1e38c9-dcb7-443c-a745-91b97ac28ccc": "Integer iterator",
                    "2d0ce8b9-c9c3-43ce-ad2f-ad493898de37": "Probe Sensor - Integer",
                    "445b44d1-59b3-425c-ac48-7c13e0f2ea5b": "Probe Sensor - Integer_2",
                    "d76fca06-f050-4790-88a8-0aac10c87b39": "Boolean Parameter",
                },
                "values": {
                    "0f1e38c9-dcb7-443c-a745-91b97ac28ccc": {
                        "out_1": 1,
                        "out_2": [3, 4],
                    },
                    "2d0ce8b9-c9c3-43ce-ad2f-ad493898de37": {"in_1": 7},
                    "445b44d1-59b3-425c-ac48-7c13e0f2ea5b": {"in_1": 1},
                    "d76fca06-f050-4790-88a8-0aac10c87b39": {"out_1": True},
                },
            }
        }


def extract_project_results(workbench: dict[str, Any]) -> ExtractedResults:
    """Extracting results from a project's workbench section (i.e. pipeline).  Specifically:

    - data sources (e.g. outputs from iterators, paramters)
    - progress of evaluators (e.g. a computational service)
    - data observers (basically inputs from probes)

    NOTE: all projects produces from iterations preserve the same node uuids so
    running this extraction on all projects from a iterations allows to create a
    row for a table of results
    """
    # nodeid -> % progress
    progress = {}
    # nodeid -> label (this map is necessary because cannot guaratee labels to be unique)
    labels = {}
    # nodeid -> { port: value , ...} # results have two levels deep: node/port
    results = {}

    for noid, node in workbench.items():
        key_parts = node["key"].split("/")

        # evaluate progress
        if "comp" in key_parts:
            progress[noid] = node.get("progress", 0)

        # evaluate results
        if "probe" in key_parts:
            label = node["label"]
            values = {}
            for port_name, node_input in node["inputs"].items():
                try:
                    values[port_name] = workbench[node_input["nodeUuid"]]["outputs"][
                        node_input["output"]
                    ]
                except KeyError:
                    # if not run, we know name but NOT value
                    values[port_name] = "n/a"
            results[noid], labels[noid] = values, label

        elif "data-iterator" in key_parts:
            label = node["label"]
            try:
                values = node["outputs"]  # {oid: value, ...}
            except KeyError:
                # if not iterated, we do not know NEITHER name NOT values
                values = {}
            results[noid], labels[noid] = values, label

        elif "parameter" in key_parts:
            label = node["label"]
            values = node["outputs"]
            results[noid], labels[noid] = values, label

    res = ExtractedResults(progress=progress, labels=labels, values=results)  # type: ignore[arg-type]
    return res

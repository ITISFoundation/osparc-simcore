# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json


def test_it():

    workbench = {
        "0f1e38c9-dcb7-443c-a745-91b97ac28ccc": {
            "key": "simcore/services/frontend/data-iterator/funky-range",
            "version": "1.0.0",
            "label": "Integer iterator",
            "inputs": {"linspace_start": 0, "linspace_stop": 2, "linspace_step": 1},
            "inputNodes": [],
            # some funky output of iterator/param,
            "outputs": {"out_1": 1, "out_2": [3, 4]},
        },
        "e33c6880-1b1d-4419-82d7-270197738aa9": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.0.0",
            "label": "sleeper",
            "inputs": {
                "input_2": {
                    "nodeUuid": "0f1e38c9-dcb7-443c-a745-91b97ac28ccc",
                    "output": "out_1",
                },
                "input_3": False,
            },
            "inputNodes": ["0f1e38c9-dcb7-443c-a745-91b97ac28ccc"],
            "state": {
                "currentStatus": "SUCCESS",
                "modified": False,
                "dependencies": [],
            },
            "progress": 100,
            "outputs": {
                "output_1": {
                    "store": "0",
                    "path": "30359da5-ca4d-3288-a553-5f426a204fe6/e33c6880-1b1d-4419-82d7-270197738aa9/single_number.txt",
                    "eTag": "a87ff679a2f3e71d9181a67b7542122c",
                },
                "output_2": 7,
            },
            "runHash": "f92d1836aa1b6b1b031f9e1b982e631814708675c74ba5f02161e0f256382b2b",
        },
        "4c08265a-427b-4ac3-9eab-1d11c822ada4": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.0.0",
            "label": "sleeper",
            "inputNodes": [],
        },
        "2d0ce8b9-c9c3-43ce-ad2f-ad493898de37": {
            "key": "simcore/services/frontend/iterator-consumer/probe/int",
            "version": "1.0.0",
            "label": "Probe Sensor - Integer",
            "inputs": {
                "in_1": {
                    "nodeUuid": "e33c6880-1b1d-4419-82d7-270197738aa9",
                    "output": "output_2",
                }
            },
            "inputNodes": ["e33c6880-1b1d-4419-82d7-270197738aa9"],
        },
        "445b44d1-59b3-425c-ac48-7c13e0f2ea5b": {
            "key": "simcore/services/frontend/iterator-consumer/probe/int",
            "version": "1.0.0",
            "label": "Probe Sensor - Integer_2",
            "inputs": {
                "in_1": {
                    "nodeUuid": "0f1e38c9-dcb7-443c-a745-91b97ac28ccc",
                    "output": "out_1",
                }
            },
            "inputNodes": ["0f1e38c9-dcb7-443c-a745-91b97ac28ccc"],
        },
        "d76fca06-f050-4790-88a8-0aac10c87b39": {
            "key": "simcore/services/frontend/parameter/boolean",
            "version": "1.0.0",
            "label": "Boolean Parameter",
            "inputs": {},
            "inputNodes": [],
            "outputs": {"out_1": True},
        },
    }

    # table : Name, Pogress, Labels.... ,
    # all projects are guaranted to be topologically identical (i.e. same node uuids )

    progress = {}

    labels = {}  # nodeid -> label # NOTE labels are not uniqu
    results = (
        {}
    )  # nodeid -> { port: value , ...} # results have two levels deep: node/port
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

    print(json.dumps(labels, indent=1))
    print(json.dumps(results, indent=1))

    # this has to be something that shall be deployable in a table
    assert progress == {
        "4c08265a-427b-4ac3-9eab-1d11c822ada4": 0,
        "e33c6880-1b1d-4419-82d7-270197738aa9": 100,
    }

    # labels are not unique, so there is a map to nodeids
    assert labels == {
        "0f1e38c9-dcb7-443c-a745-91b97ac28ccc": "Integer iterator",
        "2d0ce8b9-c9c3-43ce-ad2f-ad493898de37": "Probe Sensor - Integer",
        "445b44d1-59b3-425c-ac48-7c13e0f2ea5b": "Probe Sensor - Integer_2",
        "d76fca06-f050-4790-88a8-0aac10c87b39": "Boolean Parameter",
    }
    # this is basically a tree that defines columns
    assert results == {
        "0f1e38c9-dcb7-443c-a745-91b97ac28ccc": {"out_1": 1, "out_2": [3, 4]},
        "2d0ce8b9-c9c3-43ce-ad2f-ad493898de37": {"in_1": 7},
        "445b44d1-59b3-425c-ac48-7c13e0f2ea5b": {"in_1": 1},
        "d76fca06-f050-4790-88a8-0aac10c87b39": {"out_1": True},
    }


# t
# Labels = Dict[NodeID, str]
# NodeResults = Dict[PortName, Any]
# ProjectResults = Dict[NodeID, NodeResults]

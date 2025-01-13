# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import json
from typing import Any

import pytest
from pydantic import BaseModel
from simcore_service_webserver.meta_modeling._results import (
    ExtractedResults,
    extract_project_results,
)


@pytest.fixture
def fake_workbench() -> dict[str, Any]:
    return {
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


def test_extract_project_results(fake_workbench: dict[str, Any]):

    results = extract_project_results(fake_workbench)

    print(json.dumps(results.progress, indent=1))
    print(json.dumps(results.labels, indent=1))
    print(json.dumps(results.values, indent=1))

    # this has to be something that shall be deployable in a table
    assert results.progress == {
        "4c08265a-427b-4ac3-9eab-1d11c822ada4": 0,
        "e33c6880-1b1d-4419-82d7-270197738aa9": 100,
    }

    # labels are not unique, so there is a map to nodeids
    assert results.labels == {
        "0f1e38c9-dcb7-443c-a745-91b97ac28ccc": "Integer iterator",
        "2d0ce8b9-c9c3-43ce-ad2f-ad493898de37": "Probe Sensor - Integer",
        "445b44d1-59b3-425c-ac48-7c13e0f2ea5b": "Probe Sensor - Integer_2",
        "d76fca06-f050-4790-88a8-0aac10c87b39": "Boolean Parameter",
    }
    # this is basically a tree that defines columns
    assert results.values == {
        "0f1e38c9-dcb7-443c-a745-91b97ac28ccc": {"out_1": 1, "out_2": [3, 4]},
        "2d0ce8b9-c9c3-43ce-ad2f-ad493898de37": {"in_1": 7},
        "445b44d1-59b3-425c-ac48-7c13e0f2ea5b": {"in_1": 1},
        "d76fca06-f050-4790-88a8-0aac10c87b39": {"out_1": True},
    }


@pytest.mark.parametrize(
    "model_cls",
    [ExtractedResults],
)
def test_models_examples(
    model_cls: type[BaseModel], model_cls_examples: dict[str, Any]
):
    for name, example in model_cls_examples.items():
        print(name, ":", json.dumps(example, indent=1))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"

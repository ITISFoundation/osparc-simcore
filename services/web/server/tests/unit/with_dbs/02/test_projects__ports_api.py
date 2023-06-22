# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from models_library.projects_nodes import Node, NodeID
from models_library.utils.json_schema import jsonschema_validate_schema
from pydantic import parse_obj_as
from simcore_service_webserver.projects._ports_api import (
    InvalidInputValue,
    get_project_inputs,
    get_project_outputs,
    iter_project_ports,
    set_project_inputs,
)


@pytest.fixture
def workbench_db_column() -> dict[str, Any]:
    return {
        "13220a1d-a569-49de-b375-904301af9295": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.4",
            "label": "sleeper",
            "inputs": {
                "input_2": {
                    "nodeUuid": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
                    "output": "out_1",
                },
                "input_3": False,
                "input_4": 0,
            },
            "inputsUnits": {},
            "inputNodes": ["38a0d401-af4b-4ea7-ab4c-5005c712a546"],
            "parent": None,
            "thumbnail": "",
        },
        "38a0d401-af4b-4ea7-ab4c-5005c712a546": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "X",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": 43},
            "runHash": None,
        },
        "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa": {
            "key": "simcore/services/comp/itis/sleeper",
            "version": "2.1.4",
            "label": "sleeper_2",
            "inputs": {
                "input_2": 2,
                "input_3": {
                    "nodeUuid": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
                    "output": "out_1",
                },
                "input_4": {
                    "nodeUuid": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                    "output": "out_1",
                },
            },
            "inputsUnits": {},
            "inputNodes": [
                "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
                "7bf0741f-bae4-410b-b662-fc34b47c27c9",
            ],
            "parent": None,
            "thumbnail": "",
            "state": {"currentStatus": "SUCCESS"},
            "progress": 100,
            "outputs": {
                "output_1": {
                    "store": 0,
                    "path": "e08316a8-5afc-11ed-bab7-02420a00002b/08d15a6c-ae7b-4ea1-938e-4ce81a360ffa/single_number.txt",
                    "eTag": "1679091c5a880faf6fb5e6087eb1b2dc",
                },
                "output_2": 6,
            },
            "runHash": "5d55ebe569aa0abeb5287104dc5989eabc755f160c9a5c9a1cc783fe1e058b66",
        },
        "fc48252a-9dbb-4e07-bf9a-7af65a18f612": {
            "key": "simcore/services/frontend/parameter/integer",
            "version": "1.0.0",
            "label": "Z",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": 1},
            "runHash": None,
        },
        "7bf0741f-bae4-410b-b662-fc34b47c27c9": {
            "key": "simcore/services/frontend/parameter/boolean",
            "version": "1.0.0",
            "label": "on",
            "inputs": {},
            "inputsUnits": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {"out_1": False},
            "runHash": None,
        },
        "09fd512e-0768-44ca-81fa-0cecab74ec1a": {
            "key": "simcore/services/frontend/iterator-consumer/probe/integer",
            "version": "1.0.0",
            "label": "Random sleep interval_2",
            "inputs": {
                "in_1": {
                    "nodeUuid": "13220a1d-a569-49de-b375-904301af9295",
                    "output": "output_2",
                }
            },
            "inputsUnits": {},
            "inputNodes": ["13220a1d-a569-49de-b375-904301af9295"],
            "parent": None,
            "thumbnail": "",
        },
        "76f607b4-8761-4f96-824d-cab670bc45f5": {
            "key": "simcore/services/frontend/iterator-consumer/probe/integer",
            "version": "1.0.0",
            "label": "Random sleep interval",
            "inputs": {
                "in_1": {
                    "nodeUuid": "08d15a6c-ae7b-4ea1-938e-4ce81a360ffa",
                    "output": "output_2",
                }
            },
            "inputsUnits": {},
            "inputNodes": ["08d15a6c-ae7b-4ea1-938e-4ce81a360ffa"],
            "parent": None,
            "thumbnail": "",
        },
    }


@pytest.fixture
def workbench(workbench_db_column: dict[str, Any]) -> dict[NodeID, Node]:
    # convert to  model
    return parse_obj_as(dict[NodeID, Node], workbench_db_column)


def test_get_and_set_project_inputs(workbench: dict[NodeID, Node]):

    # get all inputs in the workbench
    project_inputs: dict[NodeID, Any] = get_project_inputs(workbench=workbench)

    assert project_inputs
    assert len(project_inputs) == 3

    # check input invariants
    for node_id in project_inputs:
        input_node = workbench[node_id]

        # has no inputs
        assert not input_node.inputs
        # has only one output called out_1
        assert input_node.outputs
        assert list(input_node.outputs.keys()) == ["out_1"]

    # update
    input_port_ids = list(project_inputs.keys())
    assert len(input_port_ids) == 3
    input_0 = input_port_ids[0]
    input_1 = input_port_ids[1]
    input_2 = input_port_ids[2]

    modified = set_project_inputs(
        workbench=workbench, update={input_0: 42, input_1: 3, input_2: False}
    )
    assert modified == {input_0, input_1}
    assert get_project_inputs(workbench=workbench) == {
        input_0: 42,
        input_1: 3,
        input_2: False,
    }

    with pytest.raises(InvalidInputValue):
        set_project_inputs(
            workbench=workbench, update={input_2: "THIS SHOULD HAVE BEEN A BOOL"}
        )


def test_get_project_outputs(workbench: dict[NodeID, Node]):

    # get all outputs in the workbench
    project_outputs: dict[NodeID, Any] = get_project_outputs(workbench=workbench)

    assert project_outputs
    assert len(project_outputs) == 2

    # check output node invariant
    for node_id in project_outputs:
        output_node = workbench[node_id]

        # has no outputs
        assert not output_node.outputs
        # has only one input called in_1
        assert output_node.inputs
        assert list(output_node.inputs.keys()) == ["in_1"]


def test_project_port_get_schema(workbench):

    for port in iter_project_ports(workbench):
        # eval json-schema
        schema = port.get_schema()
        assert schema

        # should not raise
        jsonschema_validate_schema(schema=schema)

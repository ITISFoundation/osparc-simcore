# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any

import pytest
from models_library.projects_nodes import Node, NodeID
from models_library.utils.json_schema import jsonschema_validate_schema
from simcore_service_webserver.projects._ports_api import (
    InvalidInputValue,
    get_project_inputs,
    get_project_outputs,
    iter_project_ports,
    set_project_inputs,
)


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

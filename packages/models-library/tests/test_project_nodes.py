# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Dict

import pytest
from models_library.projects_nodes import Node
from models_library.projects_state import RunningState


@pytest.fixture()
def minimal_node_data_sample() -> Dict:
    return dict(
        key="simcore/services/dynamic/3dviewer",
        version="1.3.0-alpha",
        label="3D viewer human message",
    )


def test_create_minimal_node(minimal_node_data_sample):
    node = Node(**minimal_node_data_sample)

    # a nice way to see how the simplest node looks like
    assert node.inputs == {}
    assert node.outputs == {}
    assert node.state == RunningState.NOT_STARTED

    assert node.parent is None
    assert node.progress is None

    assert node.dict(exclude_unset=True) == minimal_node_data_sample


def test_backwards_compatibility_node_data(minimal_node_data_sample):
    old_node_data = minimal_node_data_sample
    # found some old data with this aspect
    old_node_data.update({"thumbnail": "", "state": "FAILURE"})

    node = Node(**old_node_data)

    assert node.thumbnail is None
    assert node.state == RunningState.FAILED

    assert node.dict(exclude_unset=True) != old_node_data

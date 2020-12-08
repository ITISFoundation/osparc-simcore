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
        version="1.0.0",
        label="3D viewer human message",
    )


def test_create_minimal_node(minimal_node_data_sample):
    node = Node(**minimal_node_data_sample)

    assert node.inputs == {}
    assert node.outputs == {}
    assert node.state == RunningState.NOT_STARTED


def test_backwards_compatibility_node_data(minimal_node_data_sample):
    old_node_data = minimal_node_data_sample
    # found some old data with this aspect
    old_node_data.update(thumbnail="", state="FAILURE")  # <----  # <----

    node = Node(**old_node_data)

    assert node.thumbnail is None
    assert node.state == RunningState.FAILED

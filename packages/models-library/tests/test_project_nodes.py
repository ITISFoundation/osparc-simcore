# pylint:disable=no-member
# pylint:disable=redefined-outer-name
# pylint:disable=unused-argument
# pylint:disable=unused-variable

from typing import Any

import pytest
from models_library.projects_nodes import Node
from models_library.projects_state import RunningState


@pytest.fixture()
def minimal_node_data_sample() -> dict[str, Any]:
    return {
        "key": "simcore/services/dynamic/3dviewer",
        "version": "1.3.0-alpha",
        "label": "3D viewer human message",
    }


def test_create_minimal_node(minimal_node_data_sample: dict[str, Any]):
    node = Node(**minimal_node_data_sample)

    # a nice way to see how the simplest node looks like
    assert node.inputs == {}
    assert node.outputs == {}
    assert node.state.current_status == RunningState.NOT_STARTED
    assert node.state.modified is True
    assert node.state.dependencies == set()

    assert node.parent is None
    assert node.progress is None

    assert node.model_dump(exclude_unset=True) == minimal_node_data_sample


def test_create_minimal_node_with_new_data_type(
    minimal_node_data_sample: dict[str, Any]
):
    old_node_data = minimal_node_data_sample
    # found some old data with this aspect
    old_node_data.update(
        {
            "thumbnail": "https://www.google.com/imgres?imgurl=https%3A%2F%2Fregtechassociation.org%2Fwp-content%2Fuploads%2F2018%2F10%2FStandards-stock-image-1400x650.jpg&imgrefurl=https%3A%2F%2Fregtechassociation.org%2Fnews%2Firta-launches-new-open-standard-principles-for-regtech-firms-in-support-of-key-initiatives-for-2018-19%2Fstandards-stock-image-1400x650%2F&tbnid=se_y-TktvwvEMM&vet=12ahUKEwjmsNDs66ruAhWEtqQKHSLRBT8QMygBegUIARCEAQ..i&docid=UiHvpBPeE3G8KM&w=1400&h=650&q=standard%20image&ved=2ahUKEwjmsNDs66ruAhWEtqQKHSLRBT8QMygBegUIARCEAQ",
            "state": {"currentStatus": "STARTED"},
        }
    )

    node = Node(**old_node_data)
    assert (
        node.thumbnail
        == "https://www.google.com/imgres?imgurl=https%3A%2F%2Fregtechassociation.org%2Fwp-content%2Fuploads%2F2018%2F10%2FStandards-stock-image-1400x650.jpg&imgrefurl=https%3A%2F%2Fregtechassociation.org%2Fnews%2Firta-launches-new-open-standard-principles-for-regtech-firms-in-support-of-key-initiatives-for-2018-19%2Fstandards-stock-image-1400x650%2F&tbnid=se_y-TktvwvEMM&vet=12ahUKEwjmsNDs66ruAhWEtqQKHSLRBT8QMygBegUIARCEAQ..i&docid=UiHvpBPeE3G8KM&w=1400&h=650&q=standard%20image&ved=2ahUKEwjmsNDs66ruAhWEtqQKHSLRBT8QMygBegUIARCEAQ"
    )

    assert node.state.current_status == RunningState.STARTED
    assert node.state.modified is True
    assert node.state.dependencies == set()


def test_backwards_compatibility_node_data(minimal_node_data_sample: dict[str, Any]):
    old_node_data = minimal_node_data_sample
    # found some old data with this aspect
    old_node_data.update({"thumbnail": "", "state": "FAILURE"})

    node = Node(**old_node_data)

    assert node.thumbnail is None
    assert node.state.current_status == RunningState.FAILED
    assert node.state.modified is True
    assert node.state.dependencies == set()

    assert node.model_dump(exclude_unset=True) != old_node_data

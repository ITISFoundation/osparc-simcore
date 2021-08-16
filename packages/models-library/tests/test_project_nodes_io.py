# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pprint import pformat
from typing import Any, Dict

import pytest
from models_library.projects_nodes import Node, PortLink
from models_library.projects_nodes_io import DatCoreFileLink, SimCoreFileLink


@pytest.fixture()
def minimal_simcore_file_link() -> Dict[str, Any]:
    return dict(
        store=0,
        path="/some/path/to/a/file.ext",
    )


def test_simcore_file_link_default_label(minimal_simcore_file_link: Dict[str, Any]):
    simcore_file_link = SimCoreFileLink(**minimal_simcore_file_link)

    assert simcore_file_link.store == str(minimal_simcore_file_link["store"])
    assert simcore_file_link.path == minimal_simcore_file_link["path"]
    assert simcore_file_link.label == "file.ext"
    assert simcore_file_link.e_tag == None


def test_simcore_file_link_with_label(minimal_simcore_file_link: Dict[str, Any]):
    old_link = minimal_simcore_file_link
    old_link.update({"label": "some new label that is amazing"})
    simcore_file_link = SimCoreFileLink(**old_link)

    assert simcore_file_link.store == str(minimal_simcore_file_link["store"])
    assert simcore_file_link.path == minimal_simcore_file_link["path"]
    assert simcore_file_link.label == "some new label that is amazing"
    assert simcore_file_link.e_tag == None


@pytest.mark.parametrize("model_cls", (SimCoreFileLink, DatCoreFileLink))
def test_project_nodes_io_model_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))

        model_instance = model_cls(**example)

        assert model_instance, f"Failed with {name}"
        print(name, ":", model_instance)


def test_store_discriminator():
    workbench = {
        "89f95b67-a2a3-4215-a794-2356684deb61": {
            "key": "simcore/services/frontend/file-picker",
            "version": "1.0.0",
            "label": "File Picker",
            "inputs": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {
                "outFile": {
                    "store": 1,
                    "dataset": "N:dataset:ea2325d8-46d7-4fbd-a644-30f6433070b4",
                    "path": "N:package:32df09ba-e8d6-46da-bd54-f696157de6ce",
                    "label": "initial_WTstates",
                }
            },
            "progress": 100,
            "runHash": None,
        },
        "88119776-e869-4df2-a529-4aae9d9fa35c": {
            "key": "simcore/services/dynamic/raw-graphs",
            "version": "2.10.6",
            "label": "2D plot",
            "inputs": {
                "input_1": {
                    "nodeUuid": "89f95b67-a2a3-4215-a794-2356684deb61",
                    "output": "outFile",
                }
            },
            "inputNodes": ["89f95b67-a2a3-4215-a794-2356684deb61"],
            "parent": None,
            "thumbnail": "",
        },
        "75c1707c-ec1c-49ac-a7bf-af6af9088f38": {
            "key": "simcore/services/frontend/file-picker",
            "version": "1.0.0",
            "label": "File Picker_2",
            "inputs": {},
            "inputNodes": [],
            "parent": None,
            "thumbnail": "",
            "outputs": {
                "outFile": {
                    "store": "0",
                    "dataset": "05e9404a-acb4-11e9-bf0f-02420aff77ac",
                    "path": "05e9404a-acb4-11e9-bf0f-02420aff77ac/4b3ac665-f692-5f7f-8b27-dadcb3f77260/output.csv",
                    "label": "output.csv",
                }
            },
            "progress": 100,
            "runHash": None,
        },
    }

    datacore_node = Node.parse_obj(workbench["89f95b67-a2a3-4215-a794-2356684deb61"])
    rawgraph_node = Node.parse_obj(workbench["88119776-e869-4df2-a529-4aae9d9fa35c"])
    simcore_node = Node.parse_obj(workbench["75c1707c-ec1c-49ac-a7bf-af6af9088f38"])

    # must cast to the right subclass within project_nodes.py's InputTypes and OutputTypes unions
    assert isinstance(datacore_node.outputs["outFile"], DatCoreFileLink)
    assert isinstance(simcore_node.outputs["outFile"], SimCoreFileLink)

    assert isinstance(rawgraph_node.inputs["input_1"], PortLink)

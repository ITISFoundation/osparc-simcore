# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from typing import Any

import pytest
from faker import Faker
from models_library.projects_nodes import Node, PortLink
from models_library.projects_nodes_io import (
    DatCoreFileLink,
    SimCoreFileLink,
    SimcoreS3DirectoryID,
)
from pydantic import TypeAdapter, ValidationError


@pytest.fixture()
def minimal_simcore_file_link(faker: Faker) -> dict[str, Any]:
    return {"store": 0, "path": f"{faker.uuid4()}/{faker.uuid4()}/file.ext"}


def test_simcore_file_link_default_label(minimal_simcore_file_link: dict[str, Any]):
    simcore_file_link = SimCoreFileLink(**minimal_simcore_file_link)

    assert simcore_file_link.store == minimal_simcore_file_link["store"]
    assert simcore_file_link.path == minimal_simcore_file_link["path"]
    assert simcore_file_link.label == "file.ext"
    assert simcore_file_link.e_tag is None


def test_simcore_file_link_with_label(minimal_simcore_file_link: dict[str, Any]):
    old_link = minimal_simcore_file_link
    old_link.update({"label": "some new label that is amazing"})
    simcore_file_link = SimCoreFileLink(**old_link)

    assert simcore_file_link.store == minimal_simcore_file_link["store"]
    assert simcore_file_link.path == minimal_simcore_file_link["path"]
    assert simcore_file_link.label == "some new label that is amazing"
    assert simcore_file_link.e_tag is None


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
                    "store": 0,
                    "dataset": "05e9404a-acb4-11e9-bf0f-02420aff77ac",
                    "path": "05e9404a-acb4-11e9-bf0f-02420aff77ac/4b3ac665-f692-5f7f-8b27-dadcb3f77260/output.csv",
                    "label": "output.csv",
                }
            },
            "progress": 100,
            "runHash": None,
        },
    }

    datacore_node = Node.model_validate(
        workbench["89f95b67-a2a3-4215-a794-2356684deb61"]
    )
    rawgraph_node = Node.model_validate(
        workbench["88119776-e869-4df2-a529-4aae9d9fa35c"]
    )
    simcore_node = Node.model_validate(
        workbench["75c1707c-ec1c-49ac-a7bf-af6af9088f38"]
    )

    # must cast to the right subclass within project_nodes.py's InputTypes and OutputTypes unions
    assert datacore_node.outputs
    assert isinstance(datacore_node.outputs["outFile"], DatCoreFileLink)
    assert simcore_node.outputs
    assert isinstance(simcore_node.outputs["outFile"], SimCoreFileLink)
    assert rawgraph_node.inputs
    assert isinstance(rawgraph_node.inputs["input_1"], PortLink)


UUID_0: str = "00000000-0000-0000-0000-000000000000"


def test_simcore_s3_directory_id():
    # the only allowed path is the following
    result = TypeAdapter(SimcoreS3DirectoryID).validate_python(
        f"{UUID_0}/{UUID_0}/ok-simcore-dir/"
    )
    assert result == f"{UUID_0}/{UUID_0}/ok-simcore-dir/"

    # re-parsing must work the same thing works
    assert TypeAdapter(SimcoreS3DirectoryID).validate_python(result)

    # all below are not allowed
    for invalid_path in (
        f"{UUID_0}/{UUID_0}/a-file",
        f"{UUID_0}/{UUID_0}/a-dir/a-file",
    ):
        with pytest.raises(ValidationError):
            TypeAdapter(SimcoreS3DirectoryID).validate_python(invalid_path)

    with pytest.raises(ValidationError, match="Not allowed subdirectory found in"):
        TypeAdapter(SimcoreS3DirectoryID).validate_python(
            f"{UUID_0}/{UUID_0}/a-dir/a-subdir/"
        )


@pytest.mark.parametrize(
    "s3_object, expected",
    [
        (
            f"{UUID_0}/{UUID_0}/just-a-dir/",
            f"{UUID_0}/{UUID_0}/just-a-dir/",
        ),
        (
            f"{UUID_0}/{UUID_0}/a-dir/a-file",
            f"{UUID_0}/{UUID_0}/a-dir/",
        ),
        (
            f"{UUID_0}/{UUID_0}/a-dir/another-dir/a-file",
            f"{UUID_0}/{UUID_0}/a-dir/",
        ),
        (
            f"{UUID_0}/{UUID_0}/a-dir/a/b/c/d/e/f/g/h/file.py",
            f"{UUID_0}/{UUID_0}/a-dir/",
        ),
    ],
)
def test_simcore_s3_directory_id_from_simcore_s3_file_id(s3_object: str, expected: str):
    result = SimcoreS3DirectoryID.from_simcore_s3_object(s3_object)
    assert f"{result}" == expected


def test_simcore_s3_directory_get_parent():
    # pylint: disable=protected-access

    with pytest.raises(ValueError, match="does not have enough parents, expected 4"):
        SimcoreS3DirectoryID._get_parent("hello/object", parent_index=4)  # noqa SLF001

    with pytest.raises(ValueError, match="does not have enough parents, expected 4"):
        SimcoreS3DirectoryID._get_parent("hello/object/", parent_index=4)  # noqa SLF001
    with pytest.raises(ValueError, match="does not have enough parents, expected 4"):
        SimcoreS3DirectoryID._get_parent(  # noqa SLF001
            "/hello/object/", parent_index=4
        )

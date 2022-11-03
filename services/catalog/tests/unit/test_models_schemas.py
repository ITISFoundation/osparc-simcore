# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from pprint import pformat

import pytest
from models_library.services import ServiceInput
from simcore_service_catalog.models.schemas.services import (
    ServiceGet,
    ServiceItem,
    ServiceUpdate,
)
from simcore_service_catalog.models.schemas.services_ports import ServicePortGet


@pytest.mark.parametrize(
    "model_cls",
    (
        ServiceGet,
        ServiceUpdate,
        ServiceItem,
        ServicePortGet,
    ),
)
def test_service_api_models_examples(model_cls, model_cls_examples):
    for name, example in model_cls_examples.items():
        print(name, ":", pformat(example))
        model_instance = model_cls(**example)
        assert model_instance, f"Failed with {name}"


def test_service_port_with_file():

    io = ServiceInput.parse_obj(
        {
            "displayOrder": 1,
            "label": "Input files",
            "description": "Files downloaded from service connected at the input",
            "type": "data:*/*",  # < --- generic mimetype!
            "fileToKeyMap": {
                "single_number.txt": "input_1"
            },  # <-- provides a file with an extension
        }
    )

    port = ServicePortGet.from_service_io("input", "input_1", io).dict(
        exclude_unset=True
    )

    assert port == {
        "key": "input_1",
        "kind": "input",
        "content_media_type": "text/plain",  # <-- deduced from extension
        "content_schema": {
            "type": "string",
            "title": "Input files",
            "description": "Files downloaded from service connected at the input",
        },
    }


def test_service_port_with_boolean():

    io = ServiceInput.parse_obj(
        {
            "displayOrder": 3,
            "label": "Same title and description is more usual than you might think",
            "description": "Same title and description is more usual than you might think",  # <- same label and description!
            "type": "boolean",
            "defaultValue": False,  # <- has a default
        }
    )

    port = ServicePortGet.from_service_io("input", "input_1", io).dict(
        exclude_unset=True
    )

    assert port == {
        "key": "input_1",
        "kind": "input",
        # "content_media_type": None,  # <-- no content media
        "content_schema": {
            "type": "boolean",
            "title": "Same title and description is more usual than you might think",  # <-- no description
            "default": False,  # <--
        },
    }

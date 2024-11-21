# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from models_library.api_schemas_catalog.services_ports import ServicePortGet
from models_library.services import ServiceInput


def test_service_port_with_file():

    io = ServiceInput.model_validate(
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

    port = ServicePortGet.from_service_io("input", "input_1", io).model_dump(
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

    io = ServiceInput.model_validate(
        {
            "displayOrder": 3,
            "label": "Same title and description is more usual than you might think",
            "description": "Same title and description is more usual than you might think",  # <- same label and description!
            "type": "boolean",
            "defaultValue": False,  # <- has a default
        }
    )

    port = ServicePortGet.from_service_io("input", "input_1", io).model_dump(
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

""" This test suite does not intend to re-test pydantic but rather
check some "corner cases" or critical setups with pydantic model such that:

- we can ensure a given behaviour is preserved through updates
- document/clarify some concept

"""

from typing import Union, get_args, get_origin

import pytest
from models_library.projects_nodes import InputTypes, OutputTypes
from models_library.projects_nodes_io import SimCoreFileLink
from pydantic import BaseModel, ValidationError, schema_json_of
from pydantic.types import Json

# NOTE: pydantic at a glance (just a few key features):
#
# structured data  -->| (parse+validate) --> [ Model.fields ] --> (export)                       |--> structured data
# - no guarantees         - map (alias)       - accessors        - filter (include/exclude ...)       - w/ guarantees
#                         - ...               - doc              - map (by_alias, copy&udpate )
#                                                                - format (json, dict)
#
# NOTE: think of the direction of data in a pydantic model. It defines how the field contraints are defined! The
#    model does not necessarily can be used in the opposite direction. e.g. cannot always use the same model
#    to read from a database and to write in it.
#


def test_json_type():
    # Json data type first load a raw JSON string and parses it into a nested dict
    # SEE https://pydantic-docs.helpmanual.io/usage/types/#json-type

    class ArgumentAnnotation(BaseModel):
        name: str
        data_schema: Json

    # notice that this is a raw string!
    jsonschema_of_x = schema_json_of(list[int], title="schema[x]")
    assert isinstance(jsonschema_of_x, str)

    x_annotation = ArgumentAnnotation(name="x", data_schema=jsonschema_of_x)

    # x_schema was parsed as a string into a nested dict
    assert x_annotation.data_schema != jsonschema_of_x
    assert x_annotation.data_schema == {
        "title": "schema[x]",
        "type": "array",
        "items": {"type": "integer"},
    }

    assert x_annotation.dict() == {
        "name": "x",
        "data_schema": {
            "title": "schema[x]",
            "type": "array",
            "items": {"type": "integer"},
        },
    }

    # Notice how this model is not "reversable", i.e. exported outputs
    # cannot be used as inputs again
    #
    # the constructor would expect a raw string but we produced a nested dict
    with pytest.raises(ValidationError) as exc_info:
        ArgumentAnnotation(**x_annotation.dict())

    assert exc_info.value.errors()[0] == {
        "loc": ("data_schema",),
        "msg": "JSON object must be str, bytes or bytearray",
        "type": "type_error.json",
    }

    with pytest.raises(ValidationError) as exc_info:
        ArgumentAnnotation(name="foo", data_schema="invalid-json")

    assert exc_info.value.errors()[0] == {
        "loc": ("data_schema",),
        "msg": "Invalid JSON",
        "type": "value_error.json",
    }


def test_union_types_coercion():
    # SEE https://pydantic-docs.helpmanual.io/usage/types/#unions
    class Func(BaseModel):
        input: InputTypes
        output: OutputTypes

    assert get_origin(InputTypes) is Union
    assert get_origin(OutputTypes) is Union
    #
    # pydantic will attempt to 'match' any of the types defined under Union and will use the first one that matches
    # NOTE: it is recommended that, when defining Union annotations, the most specific type is included first and followed by less specific types.
    #

    assert Func.schema()["properties"]["input"] == {
        "title": "Input",
        "anyOf": [
            {"type": "boolean"},
            {"type": "integer"},
            {"type": "number"},
            {"format": "json-string", "type": "string"},
            {"type": "string"},
            {"$ref": "#/definitions/PortLink"},
            {"$ref": "#/definitions/SimCoreFileLink"},
            {"$ref": "#/definitions/DatCoreFileLink"},
            {"$ref": "#/definitions/DownloadLink"},
            {"type": "array", "items": {}},
            {"type": "object"},
        ],
    }

    # integers ------------------------
    model = Func.parse_obj({"input": "0", "output": 1})
    print(model.json(indent=1))

    assert model.input == 0
    assert model.output == 1

    # numbers and bool ------------------------
    model = Func.parse_obj({"input": "0.5", "output": "false"})
    print(model.json(indent=1))

    assert model.input == 0.5
    assert model.output is False

    # (undefined) json string vs string ------------------------
    model = Func.parse_obj(
        {
            "input": '{"w": 42, "z": false}',  # NOTE: this is a raw json string
            "output": "some/path/or/string",
        }
    )
    print(model.json(indent=1))

    assert model.input == {"w": 42, "z": False}
    assert model.output == "some/path/or/string"

    # (undefined) json string vs SimCoreFileLink.dict() ------------
    MINIMAL = 2  # <--- index of the example with the minimum required fields
    assert SimCoreFileLink in get_args(OutputTypes)
    example = SimCoreFileLink.parse_obj(
        SimCoreFileLink.Config.schema_extra["examples"][MINIMAL]
    )
    model = Func.parse_obj(
        {
            "input": '{"w": 42, "z": false}',
            "output": example.dict(
                exclude_unset=True
            ),  # NOTE: this is NOT a raw json string
        }
    )
    print(model.json(indent=1))
    assert model.input == {"w": 42, "z": False}
    assert model.output == example
    assert isinstance(model.output, SimCoreFileLink)

    # json array and objects
    model = Func.parse_obj({"input": {"w": 42, "z": False}, "output": [1, 2, 3, None]})
    print(model.json(indent=1))
    assert model.input == {"w": 42, "z": False}
    assert model.output == [1, 2, 3, None]

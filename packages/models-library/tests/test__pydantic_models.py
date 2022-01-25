""" This test suite does not intend to re-test pydantic but rather
check some "corner cases" or critical setups with pydantic model such that:

- we can ensure a given behaviour is preserved through updates
- document/clarify some concept

"""

from typing import List

import pytest
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

    class InputArgument(BaseModel):
        name: str
        data_schema: Json

    # notice that this is a raw string!
    jsonschema_of_x = schema_json_of(List[int], title="schema[x]")
    assert isinstance(jsonschema_of_x, str)

    x_annotation = InputArgument(name="x", data_schema=jsonschema_of_x)

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
        InputArgument(**x_annotation.dict())

    assert exc_info.value.errors()[0] == {
        "loc": ("data_schema",),
        "msg": "JSON object must be str, bytes or bytearray",
        "type": "type_error.json",
    }

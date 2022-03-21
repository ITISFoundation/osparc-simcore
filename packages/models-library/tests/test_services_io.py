# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Any, Callable, Dict, Mapping, Tuple

import jsonschema
import pytest
from faker import Faker
from models_library.services import PROPERTY_TYPE_RE, ServiceInput, ServiceOutput
from pydantic import schema_of

FILE = r"data:([^/\s,]+/[^/\s,]+|\[[^/\s,]+/[^/\s,]+(,[^/\s]+/[^/,\s]+)*\]))"


VALID_PROPERTY_TYPES = [
    "number",
    "integer",
    "boolean",
    "string",
    "ref_contentSchema",
    FILE,
]
property_to_python_types = {
    "number": float,
    "integer": int,
    "boolean": bool,
    "string": str,
}

Schema = Mapping[str, Any]

# https://faker.readthedocs.io/en/master/providers/faker.providers.python.html#faker-providers-python


@pytest.fixture
def fake_number(faker: Faker) -> Tuple[float, Schema]:
    schema = schema_of(float, title="number")
    schema["x-unit"] = "m"  # TODO: fake provider with units?

    data = faker.pyfloat()  # OR faker_schema(schema)

    # raises jsonschema.ValidationError or jsonschema.SchemaError
    jsonschema.validate(data, schema)
    # TODO: add validator class to support x-unit??
    return data, schema


@pytest.fixture
def fake_integer(faker: Faker) -> Tuple[int, Schema]:
    schema = schema_of(int, title="integer")
    schema["x-unit"] = "m-m"

    data = faker.pyint()

    jsonschema.validate(data, schema)
    return data, schema


@pytest.fixture
def fake_bool(faker: Faker) -> Tuple[bool, Schema]:
    schema = schema_of(bool, title="boolean")

    data = faker.pybool()

    jsonschema.validate(data, schema)
    return data, schema


@pytest.fixture
def fake_file_link(faker: Faker) -> Tuple[float, Schema]:
    schema = schema_of(bool, title="boolean")

    data = faker.pybool()

    jsonschema.validate(data, schema)
    return data, schema


@pytest.fixture
def faker_schema(faker: Faker) -> Callable[[str], Any]:
    def go(schema: Dict[str, Any]):
        fake_fun = {
            "number": faker.pyfloat,
            "integer": faker.pyint,
            "boolean": faker.pybool,
            "string": faker.pystr,
        }
        return fake_fun[schema["type"]]()

    return go


def test_it(faker_schema: Callable):

    for property_typename, python_type in property_to_python_types.items():
        schema = schema_of(python_type, title=property_typename)
        data = faker_schema(schema)

    # ref_contentSchema
    # schema =  ##json-schema w/ and w/o units
    # data = faker_schema(schema)

    # PortLink
    # LinkToFiles

    #


# EXAMPLES = [
#     {
#         "Services.outputs[oid]": ServiceOutput.parse_obj(
#             {
#                 "label": "Time Slept",
#                 "description": "Time the service waited before completion",
#                 "type": "number",
#             }
#         ),
#         "Project.workbench[nid].outputs[oid]": 2,
#     },
#     {
#         "Services.outputs[oid]": ServiceOutput.parse_obj(
#             {
#                 "label": "Time Slept",
#                 "description": "desc",
#                 "type": "ref_contentSchema",
#                 "contentSchema":
#             }
#         ),
#         "Project.workbench[nid].outputs[oid]": 2,
#     },
# ]


def test_can_connect_output_with_input(
    from_output: ServiceOutput, to_input: ServiceInput, strict: bool
):
    pass


def test_service_types():
    assert f'^({"|".join(VALID_PROPERTY_TYPES)})$' == PROPERTY_TYPE_RE

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Union

import pytest
from models_library.services import ServiceInput, ServiceOutput
from models_library.utils.json_schema import jsonschema_validate_schema
from models_library.utils.services_io import get_service_io_json_schema

example_inputs_labels = [
    e for e in ServiceInput.Config.schema_extra["examples"] if e["label"]
]
example_outputs_labels = [
    e for e in ServiceOutput.Config.schema_extra["examples"] if e["label"]
]


@pytest.fixture(params=example_inputs_labels + example_outputs_labels)
def service_io(request: pytest.FixtureRequest) -> Union[ServiceInput, ServiceOutput]:
    try:
        index = example_inputs_labels.index(request.param)
        example = ServiceInput.Config.schema_extra["examples"][index]
        return ServiceInput.parse_obj(example)
    except ValueError:
        index = example_outputs_labels.index(request.param)
        example = ServiceOutput.Config.schema_extra["examples"][index]
        return ServiceOutput.parse_obj(example)


def test_it(service_io: Union[ServiceInput, ServiceOutput]):
    print(service_io.json(indent=2))

    # get
    schema = get_service_io_json_schema(service_io)
    print(schema)

    if service_io.property_type.startswith("data"):
        assert not schema
    else:
        assert schema

        # check valid jsons-schema
        jsonschema_validate_schema(schema)

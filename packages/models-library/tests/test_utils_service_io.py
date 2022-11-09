# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import itertools
import json
from pathlib import Path
from typing import Union

import pytest
from models_library.services import ServiceInput, ServiceOutput
from models_library.utils.json_schema import jsonschema_validate_schema
from models_library.utils.services_io import get_service_io_json_schema
from pydantic import parse_obj_as

example_inputs_labels = [
    e for e in ServiceInput.Config.schema_extra["examples"] if e["label"]
]
example_outputs_labels = [
    e for e in ServiceOutput.Config.schema_extra["examples"] if e["label"]
]


@pytest.fixture(params=example_inputs_labels + example_outputs_labels)
def service_port(request: pytest.FixtureRequest) -> Union[ServiceInput, ServiceOutput]:
    try:
        index = example_inputs_labels.index(request.param)
        example = ServiceInput.Config.schema_extra["examples"][index]
        return ServiceInput.parse_obj(example)
    except ValueError:
        index = example_outputs_labels.index(request.param)
        example = ServiceOutput.Config.schema_extra["examples"][index]
        return ServiceOutput.parse_obj(example)


def test_get_schema_from_port(service_port: Union[ServiceInput, ServiceOutput]):
    print(service_port.json(indent=2))

    # get
    schema = get_service_io_json_schema(service_port)
    print(schema)

    if service_port.property_type.startswith("data"):
        assert not schema
    else:
        assert schema
        # check valid jsons-schema
        jsonschema_validate_schema(schema)


def test_it(project_tests_dir: Path):
    data_folder = project_tests_dir / "data"

    for path in data_folder.rglob("metadata*.json"):
        print(path)
        meta = json.loads(path.read_text())

        inputs = parse_obj_as(list[ServiceInput], meta["inputs"])
        outputs = parse_obj_as(list[ServiceOutput], meta["outputs"])

        for port in itertools.chain(inputs, outputs):
            schema = get_service_io_json_schema(port)

            if port.property_type.startswith("data"):
                assert not schema
            else:
                assert schema
                # check valid jsons-schema
                jsonschema_validate_schema(schema)


# TODO: test against all image labels in master registry! and write down tests that
# fail right now or edge cases
#
#
# Build an audit tool as well to keep track of changes in models-Library inputs.outpust schemas
#

# curl -u  admin:adminadmin -X GET https://registry.osparc-master.speag.com/v2/simcore/services/comp/ascent-runner/manifests/1.0.0 | jq ".history[0].v1Compatibility"

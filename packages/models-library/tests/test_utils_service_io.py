# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import itertools
import json
import sys
from pathlib import Path
from typing import Union

import pytest
from models_library.services import ServiceInput, ServiceOutput, ServicePortKey
from models_library.utils.json_schema import jsonschema_validate_schema
from models_library.utils.services_io import get_service_io_json_schema
from pydantic import parse_obj_as
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.utils_docker_registry import download_all_registry_metadata

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


CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
TEST_DATA_FOLDER = CURRENT_DIR / "data"


@pytest.fixture(scope="module")
def metadata_test_data_dir(
    project_tests_dir: Path, mock_env_devel_environment: EnvVarsDict
):
    """
    Downloads all metadata from services to registry defined in env vars
    in
    """
    assert project_tests_dir == CURRENT_DIR
    test_data_dir = TEST_DATA_FOLDER / ".metadata-cache.keep.ignore"
    download_all_registry_metadata(dest_dir=test_data_dir)
    return test_data_dir


@pytest.mark.parametrize(
    "meta_path",
    TEST_DATA_FOLDER.rglob("metadata*.json"),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_against_service_metadata_configs(
    metadata_test_data_dir: Path, meta_path: Path
):
    """
    This tests can be used as well to validate all metadata in a given registry
    """
    assert metadata_test_data_dir in meta_path.parents

    meta = json.loads(meta_path.read_text())

    inputs = parse_obj_as(dict[ServicePortKey, ServiceInput], meta["inputs"])
    outputs = parse_obj_as(dict[ServicePortKey, ServiceOutput], meta["outputs"])

    for port in itertools.chain(inputs.values(), outputs.values()):
        schema = get_service_io_json_schema(port)

        if port.property_type.startswith("data"):
            assert not schema
        else:
            assert schema
            # check valid jsons-schema
            jsonschema_validate_schema(schema)

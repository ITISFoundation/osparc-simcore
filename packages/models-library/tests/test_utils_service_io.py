# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import itertools
import json
import re
import sys
from collections.abc import Iterable
from contextlib import suppress
from pathlib import Path

import pytest
from models_library.basic_regex import SIMPLE_VERSION_RE
from models_library.services import ServiceInput, ServiceOutput, ServicePortKey
from models_library.utils.json_schema import jsonschema_validate_schema
from models_library.utils.services_io import get_service_io_json_schema
from pydantic import TypeAdapter

example_inputs_labels = [
    e for e in ServiceInput.model_config["json_schema_extra"]["examples"] if e["label"]
]
example_outputs_labels = [
    e for e in ServiceOutput.model_config["json_schema_extra"]["examples"] if e["label"]
]


@pytest.fixture(params=example_inputs_labels + example_outputs_labels)
def service_port(request: pytest.FixtureRequest) -> ServiceInput | ServiceOutput:
    try:
        index = example_inputs_labels.index(request.param)
        example = ServiceInput.model_config["json_schema_extra"]["examples"][index]
        return ServiceInput.model_validate(example)
    except ValueError:
        index = example_outputs_labels.index(request.param)
        example = ServiceOutput.model_config["json_schema_extra"]["examples"][index]
        return ServiceOutput.model_validate(example)


def test_get_schema_from_port(service_port: ServiceInput | ServiceOutput):
    print(service_port.model_dump_json(indent=2))

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


@pytest.mark.diagnostics()
@pytest.mark.parametrize(
    "metadata_path",
    TEST_DATA_FOLDER.rglob("metadata*.json"),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_against_service_metadata_configs(metadata_path: Path):
    """
    This tests can be used as well to validate all metadata in a given registry

    SEE make pull_test_data to pull data from the registry specified in .env
    """

    meta = json.loads(metadata_path.read_text())

    inputs = TypeAdapter(dict[ServicePortKey, ServiceInput]).validate_python(
        meta["inputs"]
    )
    outputs = TypeAdapter(dict[ServicePortKey, ServiceOutput]).validate_python(
        meta["outputs"]
    )

    for port in itertools.chain(inputs.values(), outputs.values()):
        schema = get_service_io_json_schema(port)

        if port.property_type.startswith("data"):
            assert not schema
        else:
            assert schema
            # check valid jsons-schema
            jsonschema_validate_schema(schema)


assert SIMPLE_VERSION_RE[0] == "^"
assert SIMPLE_VERSION_RE[-1] == "$"
_VERSION_SEARCH_RE = re.compile(SIMPLE_VERSION_RE[1:-1])  # without $ and ^


def _iter_main_services() -> Iterable[Path]:
    """NOTE: Filters the main service when there is a group
    of services behind a node.
    """
    for p in TEST_DATA_FOLDER.rglob("metadata-*.json"):
        with suppress(Exception):
            meta = json.loads(p.read_text())
            if (meta.get("type") == "computational") or meta.get(
                "service.container-http-entrypoint"
            ):
                yield p


@pytest.mark.diagnostics()
@pytest.mark.parametrize(
    "metadata_path",
    (p for p in _iter_main_services() if "latest" not in p.name),
    ids=lambda p: f"{p.parent.name}/{p.name}",
)
def test_service_metadata_has_same_version_as_tag(metadata_path: Path):
    meta = json.loads(metadata_path.read_text())

    # metadata-M.m.b.json
    match = _VERSION_SEARCH_RE.search(metadata_path.name)
    assert match, f"tag {metadata_path.name} is not a version"
    version_in_tag = match.group()
    assert meta["version"] == version_in_tag

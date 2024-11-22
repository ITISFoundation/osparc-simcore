# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=unused-variable

from pathlib import Path

import pytest
import yaml
from utils import list_files_in_api_specs

# Conventions
_REQUIRED_FIELDS = [
    "data",
]
CONVERTED_SUFFIX = "-converted.yaml"


# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))

non_converted_yamls = [
    pathstr
    for pathstr in list_files_in_api_specs("*.yaml")
    if not f"{pathstr}".endswith(CONVERTED_SUFFIX)
]  # skip converted schemas

assert non_converted_yamls


@pytest.mark.parametrize("path", non_converted_yamls, ids=lambda p: p.name)
def test_openapi_envelope_required_fields(path: Path):
    with Path.open(path) as file_stream:
        oas_dict = yaml.safe_load(file_stream)
        for key, value in oas_dict.items():
            if "Envelope" in key:
                assert "required" in value, f"field required is missing from {path}"
                required_fields = value["required"]

                assert "properties" in value, f"field properties is missing from {path}"
                fields_definitions = value["properties"]

                assert "error" in required_fields or "data" in required_fields
                assert "error" in fields_definitions or "data" in fields_definitions

# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=unused-variable

import yaml
import pytest
import io

from utils import list_files_in_api_specs

# Conventions
_REQUIRED_FIELDS = ["error", "data"]
CONVERTED_SUFFIX = "-converted.yaml"

# TESTS ----------------------------------------------------------
# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))

non_converted_yamls = [ pathstr for pathstr in list_files_in_api_specs("*.yaml")
                                    if not pathstr.endswith(CONVERTED_SUFFIX) ]  # skip converted schemas


@pytest.mark.parametrize("path", non_converted_yamls)
def test_openapi_envelope_required_fields(path: str):
    with io.open(path) as file_stream:
        oas_dict = yaml.safe_load(file_stream)
        for key, value in oas_dict.items():
            if "Envelope" in key:
                assert "required" in value, "field required is missing from {file}".format(file=path)
                required_fields = value["required"]
                assert "properties" in value, "field properties is missing from {file}".format(file=path)
                fields_definitions = value["properties"]
                for field in _REQUIRED_FIELDS:
                    assert field in required_fields, ("field {field} is missing in {file}".format(field=field, file=path))
                    assert field in fields_definitions, ("field {field} is missing in {file}".format(field=field, file=path))


@pytest.mark.parametrize("path", non_converted_yamls)
def test_openapi_type_name(path: str):
    with io.open(path) as file_stream:
        oas_dict = yaml.safe_load(file_stream)

        for key, value in oas_dict.items():
            if "Envelope" in key:
                assert "properties" in value, ("field properties is missing from {file}".format(file=path))
                fields_definitions = value["properties"]
                for field_key, field_value in fields_definitions.items():
                    data_values = field_value
                    for data_key, data_value in data_values.items():
                        if "$ref" in data_key:
                            assert str(data_value).endswith("Type"), ("field {field} name is not finishing with Type in {file}".format(field=field_key, file=path))

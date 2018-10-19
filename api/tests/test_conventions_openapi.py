# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=unused-variable

from pathlib import Path
import yaml
import pytest

# List of conventions
_REQUIRED_FIELDS = ["error", "data"]
CONVERTED_SUFFIX = "-converted.yaml"


@pytest.fixture
def non_converted_yamls(api_specs_dir):
    return [ path for path in api_specs_dir.rglob("*.yaml")
                  if not path.name.endswith(CONVERTED_SUFFIX) ]  # skip converted schemas


def test_openapi_envelope_required_fields(non_converted_yamls):
    for path in non_converted_yamls:
        with path.open() as file_stream:
            oas_dict = yaml.safe_load(file_stream)
            for key, value in oas_dict.items():
                if "Envelope" in key:
                    assert "required" in value, "field required is missing from {file}".format(file=str(path))
                    required_fields = value["required"]
                    assert "properties" in value, "field properties is missing from {file}".format(file=str(path))
                    fields_definitions = value["properties"]
                    for field in _REQUIRED_FIELDS:
                        assert field in required_fields, ("field {field} is missing in {file}".format(field=field, file=str(path)))
                        assert field in fields_definitions, ("field {field} is missing in {file}".format(field=field, file=str(path)))


def test_openapi_type_name(non_converted_yamls):
    for path in non_converted_yamls:
        with path.open() as file_stream:
            oas_dict = yaml.safe_load(file_stream)

            for key, value in oas_dict.items():
                if "Envelope" in key:
                    assert "properties" in value, ("field properties is missing from {file}".format(file=str(path)))
                    fields_definitions = value["properties"]
                    for field_key, field_value in fields_definitions.items():
                        data_values = field_value
                        for data_key, data_value in data_values.items():
                            if "$ref" in data_key:
                                assert str(data_value).endswith("Type"), ("field {field} name is not finishing with Type in {file}".format(field=field_key, file=str(path)))

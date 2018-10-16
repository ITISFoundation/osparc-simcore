from pathlib import Path

import yaml

_API_DIR = Path(__file__).parent.parent

def test_openapi_envelope_required_fields():
    _REQUIRED_FIELDS = ["error", "data"]

    list_of_openapi_filepaths = _API_DIR.rglob("*.yaml")
    for path in list_of_openapi_filepaths:
        # skip converted schemas
        if str(path).endswith("-converted.yaml"):
            continue

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

def test_openapi_type_name():
    list_of_openapi_filepaths = _API_DIR.rglob("*.yaml")
    for path in list_of_openapi_filepaths:
        # skip converted schemas
        if str(path).endswith("-converted.yaml"):
            continue

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
                            
            

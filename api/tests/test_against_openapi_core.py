""" Tests all openapi specs against openapi-core functionality

    - Checks that openapi specs do work properly with openapi-core
    - The key issue is jsonschema RefResolver!
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from pathlib import Path

import openapi_core
import pytest
import yaml
from utils import list_all_openapi


@pytest.mark.parametrize("openapi_path", list_all_openapi())
def test_can_create_specs_from_path(openapi_path: str):
    # NOTE: get as 'str' so path fixture can be rendered in test log
    oas_path = Path(openapi_path)
    with oas_path.open() as fh:
        spec_dict = yaml.safe_load(fh)

    # will raise if openapi_core cannot handle OAS
    specs = openapi_core.Spec.from_dict(spec_dict, base_uri=oas_path.as_uri())

    assert specs
    assert isinstance(specs, openapi_core.Spec)

# pylint: disable=redefined-outer-name

import pytest
import yaml
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

from simcore_service_director import resources


@pytest.fixture
def current_openapi_specs():
    return f"{resources.RESOURCE_OPENAPI_ROOT}/openapi.yaml"


def test_openapi_specs(current_openapi_specs):
    openapi_path = resources.get_path(current_openapi_specs)
    with resources.stream(current_openapi_specs) as fh:
        specs = yaml.safe_load(fh)
        try:
            validate_spec(specs, spec_url=openapi_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail(err.message)


def test_server_specs(current_openapi_specs):
    with resources.stream(current_openapi_specs) as fh:
        specs = yaml.safe_load(fh)

        # client-sdk current limitation
        #  - hooks to first server listed in oas
        default_server = specs['servers'][0]
        assert default_server['url']=='http://{host}:{port}/{version}', "Invalid convention"

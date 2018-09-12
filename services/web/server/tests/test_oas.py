import yaml
import pytest

from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import (
    OpenAPIValidationError
)

from simcore_service_webserver import resources

def test_openapi_specs():

    name = resources.RESOURCE_OPENAPI + "/v1/openapi.yaml"
    openapi_path = resources.get_path(name)
    with resources.stream(name) as fh:
        specs = yaml.load(fh)
        try:
            validate_spec(specs, spec_url='file://%s' % openapi_path.absolute())
        except OpenAPIValidationError as err:
            pytest.fail(err.message)

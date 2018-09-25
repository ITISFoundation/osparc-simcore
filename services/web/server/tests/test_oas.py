import yaml
import pytest

from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import (
    OpenAPIValidationError
)

from simcore_service_webserver import resources

API_VERSIONS = resources.listdir(resources.RESOURCE_OPENAPI)

@pytest.mark.parametrize('version', API_VERSIONS)
def test_openapi_specs(version):
    name = resources.RESOURCE_OPENAPI + "/{}/openapi.yaml".format(version)
    openapi_path = resources.get_path(name)
    with resources.stream(name) as fh:
        specs = yaml.load(fh)
        try:
            validate_spec(specs, spec_url='file://%s' % openapi_path.absolute())
        except OpenAPIValidationError as err:
            pytest.fail(err.message)

@pytest.mark.parametrize('version', API_VERSIONS)
def test_server_specs(version):
    name = resources.RESOURCE_OPENAPI + "/{}/openapi.yaml".format(version)
    with resources.stream(name) as fh:
        specs = yaml.load(fh)

        # client-sdk current limitation
        #  - hooks to first server listed in oas
        default_server = specs['servers'][0]
        assert default_server['url']=='http://{host}:{port}/{version}', "Invalid convention"

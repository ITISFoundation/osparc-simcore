import yaml
import pytest

from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import (
    OpenAPIValidationError
)

from simcore_service_director import resources

API_VERSIONS = resources.listdir(resources.RESOURCE_OPENAPI_ROOT)

@pytest.mark.parametrize('version', API_VERSIONS)
def test_openapi_specs(version):
    name = "{root}/{version}/openapi.yaml".format(root=resources.RESOURCE_OPENAPI_ROOT, version=version)
    openapi_path = resources.get_path(name)
    with resources.stream(name) as fh:
        specs = yaml.load(fh)
        # remove json schema stuff not valid for openapi validator
        specs["paths"].pop("/services")
        specs["paths"].pop("/services/{service_key}/{service_version}")
        try:
            validate_spec(specs, spec_url=openapi_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail(err.message)

@pytest.mark.parametrize('version', API_VERSIONS)
def test_server_specs(version):
    name = "{root}/{version}/openapi.yaml".format(root=resources.RESOURCE_OPENAPI_ROOT, version=version)
    with resources.stream(name) as fh:
        specs = yaml.load(fh)

        # client-sdk current limitation
        #  - hooks to first server listed in oas
        default_server = specs['servers'][0]
        assert default_server['url']=='http://{host}:{port}/{version}', "Invalid convention"

import yaml
import pytest

from openapi_spec_validator import validate_spec, openapi_v3_spec_validator
from openapi_spec_validator.exceptions import (
    OpenAPIValidationError
)

from simcore_service_webserver import resources

API_VERSIONS = resources.listdir(resources.RESOURCE_OPENAPI)

@pytest.mark.parametrize('version', API_VERSIONS)
def test_openapi_specs(version):
    name = resources.RESOURCE_OPENAPI + "/{}/openapi.yaml".format(version)
    openapi_path = resources.get_path(name)
    spec_dict = {}
    with resources.stream(name) as fh:
        spec_dict = yaml.load(fh)

    assert len(spec_dict), "specs are empty"

    try:
        validate_spec(spec_dict, spec_url=openapi_path.as_uri())
    except OpenAPIValidationError as err:
        pytest.fail(err.message)

    # TODO: see if can improve validation errors!!!!
    #errors = list(openapi_v3_spec_validator.iter_errors(spec_dict))
    #if errors:
    #    pytest.fail(errors)



@pytest.mark.skip(reason="Temporaly disabled")
@pytest.mark.parametrize('version', API_VERSIONS)
def test_server_specs(version):
    # FIXME: what servers ins pecs? What if there are multiple versions?
    name = resources.RESOURCE_OPENAPI + "/{}/openapi.yaml".format(version)
    with resources.stream(name) as fh:
        spec_dict = yaml.load(fh)

        # client-sdk current limitation
        #  - hooks to first server listed in oas
        default_server = spec_dict['servers'][0]
        assert default_server['url']=='http://{host}:{port}/{version}', "Invalid convention"


# TODO: test all operations have operationId

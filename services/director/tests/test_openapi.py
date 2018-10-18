# W0621:Redefining name 'spec_basepath' from outer scope (line 14)
# pylint: disable=W0621

from pathlib import Path

import pkg_resources
import pytest
import yaml
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError

import simcore_service_director


API_VERSIONS = ('v0', )

@pytest.fixture
def spec_basepath():
    basepath = Path(pkg_resources.resource_filename(simcore_service_director.__name__, 'oas3'))
    return basepath


@pytest.mark.parametrize('version', API_VERSIONS)
def test_specifications(spec_basepath, version):
    spec_path = spec_basepath / "{}/openapi.yaml".format(version)

    with spec_path.open() as fh:
        specs = yaml.load(fh)
        try:
            validate_spec(specs, spec_url=spec_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail(err.message)

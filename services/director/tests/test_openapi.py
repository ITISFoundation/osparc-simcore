
from pathlib import Path

import pkg_resources
import pytest
import simcore_service_director
import yaml
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError
from simcore_service_director.resources import RESOURCE_OPEN_API


def test_specifications():
    #pylint: disable=no-value-for-parameter
    spec_path = Path( pkg_resources.resource_filename(simcore_service_director.__name__, RESOURCE_OPEN_API) )

    with spec_path.open() as fh:
        specs = yaml.safe_load(fh)
        try:
            validate_spec(specs, spec_url=spec_path.as_uri())
        except OpenAPIValidationError as err:
            pytest.fail(err.message)

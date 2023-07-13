# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pathlib import Path
from typing import Any

import openapi_core
import pytest
import yaml
from simcore_service_storage._meta import api_vtag
from simcore_service_storage.resources import storage_resources


@pytest.fixture(scope="module")
def openapi_specs():
    spec_path: Path = storage_resources.get_path(f"api/{api_vtag}/openapi.yaml")
    spec_dict: dict[str, Any] = yaml.safe_load(spec_path.read_text())
    api_specs = openapi_core.create_spec(spec_dict, spec_path.as_uri())
    return api_specs

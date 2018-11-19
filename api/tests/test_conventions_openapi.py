# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=unused-variable

import io
import re
from pathlib import Path

import pytest
import yaml
from yarl import URL

from utils import list_files_in_api_specs

# Conventions
_REQUIRED_FIELDS = ["data", ]
CONVERTED_SUFFIX = "-converted.yaml"

API_DIR_RE = re.compile(r'v(\d{1})')


# TESTS ----------------------------------------------------------
# NOTE: parametrizing tests per file makes more visible which file failed
# NOTE: to debug use the wildcard and select problematic file, e.g. list_files_in_api_specs("*log_message.y*ml"))

non_converted_yamls = [ pathstr for pathstr in list_files_in_api_specs("*.yaml")
                                    if not pathstr.endswith(CONVERTED_SUFFIX) ]  # skip converted schemas


@pytest.mark.parametrize("path", non_converted_yamls)
def test_openapi_envelope_required_fields(path: str):
    with io.open(path) as file_stream:
        oas_dict = yaml.safe_load(file_stream)
        for key, value in oas_dict.items():
            if "Envelope" in key:
                assert "required" in value, "field required is missing from {file}".format(file=path)
                required_fields = value["required"]

                assert "properties" in value, "field properties is missing from {file}".format(file=path)
                fields_definitions = value["properties"]

                assert 'error' in required_fields or 'data' in required_fields
                assert 'error' in fields_definitions or 'data' in fields_definitions



main_openapi_yamls = [ pathstr for pathstr in list_files_in_api_specs("openapi.y*ml")
                                    if not pathstr.endswith(CONVERTED_SUFFIX) ]  # skip converted schemas

@pytest.mark.parametrize("openapi_path", main_openapi_yamls)
def test_versioning_and_basepath(openapi_path):
    openapi_path = Path(openapi_path)

    # version in folder name is only major!
    assert API_DIR_RE.match(openapi_path.parent.name), "Expected e.g. service-name/v0/openapi.yaml"
    version_in_folder = int(API_DIR_RE.match(openapi_path.parent.name).groups()[0])

    with openapi_path.open() as f:
        oas_dict = yaml.safe_load(f)

    # version in specs info is M.m.n
    version_in_info = [ int(i) for i in oas_dict["info"]["version"].split(".") ]

    assert version_in_folder == version_in_info[0]

    # basepath in servers must also be as '/v0'
    for server in oas_dict["servers"]:
        kwargs = { key: value["default"] for key, value in server.get("variables", {}).items() }
        url = URL( server["url"].format(**kwargs) )
        assert url.path == "/v%d" % version_in_folder, "Wrong basepath in server: %s" % server

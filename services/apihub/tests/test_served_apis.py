# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=unused-variable
# pylint: disable=broad-except

import io
import logging
from pathlib import Path

import openapi_core
import pytest
import yaml
from aiohttp import ClientSession
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError
from requests_html import HTMLSession
from yarl import URL

log = logging.getLogger(__name__)


def verify_links(session, links):
    for link in links:
        if not "/specs/" in str(link):
            continue

        r = session.get(link)
        assert r.status_code == 200

        if "openapi.yaml" in Path(link).name:
            # full api
            with io.StringIO(r.text) as stream:
                specs_dict = yaml.safe_load(stream)
            try:
                validate_spec(specs_dict, spec_url=link)
            except OpenAPIValidationError as err:
                pytest.fail(err.message)

        #TODO: complete this part of the test by parsing to yaml and back to string (or json) to suppress newline issues
        # url_path = Path(link)
        # if ".yaml" in url_path.suffix or ".json" in url_path.suffix:
        #     # check the same file exists and compare them
        #     # apis/director/v0/openapi.yaml vs http://hostname:port/apis/director/v0/openapi.yaml
        #     parsed_url = urlparse(link)
        #     corresponding_file_path = Path(str(_ROOT_DIR) + parsed_url.path)
        #     assert corresponding_file_path.exists()

        #     with corresponding_file_path.open() as stream:
        #         assert r.text == stream.read()

        sublinks = r.html.absolute_links
        verify_links(session, sublinks)

def test_served_openapis_valid(apihub):
    base_url = apihub

    session = HTMLSession()
    r = session.get(base_url)
    assert r.status_code == 200

    links = r.html.absolute_links
    verify_links(session, links)


async def test_create_specs(osparc_simcore_api_specs, apihub):
    # TODO: ideally every iteration is a new test (check parametrization)

    for service, version, openapi_path, url_path in osparc_simcore_api_specs:
        url = URL(apihub).join( URL(url_path) )  #api/specs/${service}/${version}/openapi.yaml

        msg = "%s, "*5 % (url, service, version, openapi_path, url_path)

        # TODO: list all services with api
        async with ClientSession() as session:
            async with session.get(url) as resp:
                txt = await resp.text()

                assert resp.status == 200, msg

                with io.StringIO(txt) as f:
                    spec_dict = yaml.safe_load(f)

                with io.open(openapi_path) as f:
                    spec_dict_local = yaml.safe_load(f)

                assert spec_dict == spec_dict_local, msg

                try:
                    spec = openapi_core.create_spec(spec_dict, spec_url=str(url))
                except Exception as err:
                    pytest.fail("%s - %s" % (err, msg) )

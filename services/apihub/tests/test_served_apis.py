import io
import logging
from pathlib import Path
# from urllib.parse import urlparse

import pytest
import yaml
from openapi_spec_validator import validate_spec
from openapi_spec_validator.exceptions import OpenAPIValidationError
from requests_html import HTMLSession

log = logging.getLogger(__name__)

_ROOT_DIR = Path(__file__).parent.parent.parent.parent

def verify_links(session, links):
    for link in links:
        if "/tests/" in str(link):
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

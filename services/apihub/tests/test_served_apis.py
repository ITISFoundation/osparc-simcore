import io
import logging
import yaml
import pytest

from pathlib import Path
from requests_html import HTMLSession
from openapi_spec_validator import validate_spec, validate_spec_url
from openapi_spec_validator.exceptions import OpenAPIValidationError

log = logging.getLogger(__name__)

def verify_links(session, links):
    for link in links:
        if "/tests/" in str(link):
            continue
        r = session.get(link)
        assert r.status_code == 200

        if "openapi.yaml" in Path(link).name:
            with io.StringIO(r.text) as stream:
                specs_dict = yaml.safe_load(stream)
            try:
                validate_spec(specs_dict, spec_url=link)
            except OpenAPIValidationError as err:
                pytest.fail(err.message)

        sublinks = r.html.absolute_links
        verify_links(session, sublinks)

def test_all_openapis_valid(apihub):
    base_url = apihub

    session = HTMLSession()    
    r = session.get(base_url)
    assert r.status_code == 200

    links = r.html.absolute_links
    verify_links(session, links)
    



# def test_all_individual_openapis(apihub):
#     pass

# def test_all_individual_jsonschemas(apihub):
#     pass
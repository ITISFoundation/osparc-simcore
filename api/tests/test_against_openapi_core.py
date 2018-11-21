""" Tests all openapi specs against openapi-core functionality

    - Checks that openapi specs do work properly with openapi-core
    - The key issue is jsonschema RefResolver!
"""
# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from os.path import relpath
from pathlib import Path
from typing import Dict, Tuple

import openapi_core
import pytest
import yaml
from aiohttp import web
from aiohttp.client import ClientSession
from openapi_core.schema.specs.models import Spec as OpenApiSpec
from yarl import URL

from utils import list_all_openapi


def _load_from_path(filepath: Path) -> Tuple[Dict, str]:
    with filepath.open() as f:
        spec_dict = yaml.safe_load(f)
        return spec_dict, filepath.as_uri()


async def _load_from_url(url: URL) -> Tuple[Dict, str]:
    #TIMEOUT_SECS = 5*60
    #async with ClientSession(timeout=TIMEOUT_SECS) as session:
    async with ClientSession() as session:
        async with session.get(url) as resp:
            text = await resp.text()
            spec_dict = yaml.safe_load(text)
            return spec_dict, str(url)


@pytest.fixture
def webserver_oas(api_specs_dir):
    oas_path = api_specs_dir / "webserver/v0/openapi.yaml"
    assert oas_path.exists()
    return oas_path


@pytest.fixture
def apispecs_server(loop, aiohttp_server, api_specs_dir ):
    app = web.Application()
    app.add_routes( [web.static("/", api_specs_dir), ] )
    server = loop.run_until_complete( aiohttp_server(app) )
    return server


# TODO: see https://docs.python.org/3.7/library/multiprocessing.html to spawn a server
# in the background
#
#from http.server import HTTPServer, SimpleHTTPRequestHandler

#@pytest.fixture
#def api_server(api_specs_dir, aiohttp_unused_port):
#    address = ('', aiohttp_unused_port())
#    with HTTPServer(address,  SimpleHTTPRequestHandler) as httpd:
#        httpd.serve_forever()





# TESTS ---------------------------------------------------------------------------

@pytest.mark.parametrize("openapi_path", list_all_openapi())
def test_can_create_specs_from_path(openapi_path):
    spec_dict, spec_url = _load_from_path( Path(openapi_path))

    specs = openapi_core.create_spec(spec_dict, spec_url)

    assert specs
    assert isinstance(specs, OpenApiSpec)


@pytest.mark.skip(reason="Cannot run aiohttp_server in same thread. TODO: create separate process")
@pytest.mark.parametrize("openapi_path", list_all_openapi())
async def test_can_create_specs_from_url(openapi_path, apispecs_server, api_specs_dir):
    origin = URL.build(**{ k:getattr(apispecs_server, k) for k in ("scheme", "host", "port")})

    url = origin.with_path( relpath(openapi_path, api_specs_dir) )
    spec_dict, spec_url = await _load_from_url(url)

    #
    # jsonschema/validators.py:386: RefResolutionError makes syncronous calls
    # and cannot user an aiohttp_server fixture in the same thread
    #
    specs = openapi_core.create_spec(spec_dict, spec_url)

    assert specs, "Failed to create specs from %s " %url
    assert isinstance(specs, OpenApiSpec)

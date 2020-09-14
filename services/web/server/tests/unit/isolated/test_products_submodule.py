# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json

import pytest
from yarl import URL

from simcore_service_webserver.constants import RQ_PRODUCT_KEY
from simcore_service_webserver.products import (DEFAULT_FE_APP, FE_APPS,
                                                discover_product_middleware)


def test_every_product_has_a_frontend_app(web_client_dir):
    compile_filepath = web_client_dir / "compile.json"
    frontend_info = json.loads(compile_filepath.read_text())
    #target = next(
    #    t for t in frontend_info["targets"] if t["type"] == frontend_info["defaultTarget"]
    #)
    #frontend_outdir = webclient_dir / target["outputPath"]

    frontend_apps = [feapp["name"] for feapp in frontend_info["applications"]]
    assert set(frontend_apps) == set(FE_APPS), f"Sync with {compile_filepath}"

    default_frontend_app = next(
        feapp["name"] for feapp in frontend_info["applications"] if feapp["default"]
    )
    assert default_frontend_app == DEFAULT_FE_APP



@pytest.mark.parametrize("sample_url,expected_product", [
    ("https://tis-master.domain.io/", "tis"),
    ("https://s4l-staging.domain.com/v0/", "s4l"),
    ("https://osparc-master.domain.com/v0/projects", "osparc"),
    ("https://s4l.domain.com/", "s4l"),
    ("https://some-valid-but-undefined-product.io/", DEFAULT_FE_APP),
    ("https://sim4life.io/", "s4l"),
    ("https://ti-solutions.io/", "tis"),
    ("https://osparc.io/", "osparc"),
    ("https://staging.osparc.io/", "osparc"),
])
async def test_middleware_product_discovery(sample_url, expected_product, mocker):
    requested_url = URL(sample_url)


    # TODO: THIS IS UNFINISHED!!
    mock_request = mocker.Mocker()
    mock_request.path = str(requested_url.path)
    mock_request.host = str(requested_url.origin)

    #mock_handler =
    # emulates response = await handler(request)

    response = await discover_product_middleware(mock_request, mock_handler)

    # ensures handler is called
    request[RQ_PRODUCT_KEY] == expected_product

# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

"""
    This tests some invariants considered in the webserver code regarding
    the structure of the frontend apps produced after compiling static-webserver/client
"""

import json
from pathlib import Path

import pytest
from simcore_service_webserver.statics._constants import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)


@pytest.fixture(scope="module")
def client_compile_cfg(web_client_dir: Path) -> dict:
    compile_filepath = web_client_dir / "compile.json"
    assert compile_filepath.exists()
    return json.loads(compile_filepath.read_text())


@pytest.fixture(scope="module")
def source_boot_index_html(web_client_dir: Path) -> Path:
    index_html = web_client_dir / "source" / "boot" / "index.html"
    assert index_html.exists()
    return index_html


@pytest.fixture(scope="module")
def metadata_file(web_client_dir: Path) -> Path:
    metadata_filepath = web_client_dir / "scripts" / "apps_metadata.json"
    assert metadata_filepath.exists()
    return json.loads(metadata_filepath.read_text())


def test_expected_frontend_apps_produced_by_webclient(client_compile_cfg: dict):
    """
    tests that names in FRONTEND_APP_DEFAULT and FRONTEND_APPS_AVAILABLE
    corresponds to actual front-end apps produced by static-webserver/client
    """
    frontend_apps_in_repo = {
        feapp["name"] for feapp in client_compile_cfg["applications"]
    }

    product_names = {
        feapp["environment"]["product.name"]
        for feapp in client_compile_cfg["applications"]
    }
    assert product_names

    # test FRONTEND_APPS_AVAILABLE
    assert (
        frontend_apps_in_repo == FRONTEND_APPS_AVAILABLE
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    assert (
        frontend_apps_in_repo == FRONTEND_APPS_AVAILABLE
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    # test FRONTEND_APP_DEFAULT
    default_frontend_app = next(
        feapp["name"]
        for feapp in client_compile_cfg["applications"]
        if feapp["default"]
    )
    assert (
        default_frontend_app == FRONTEND_APP_DEFAULT
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    assert FRONTEND_APP_DEFAULT in FRONTEND_APPS_AVAILABLE


def test_expected_frontend_apps_metadata(client_compile_cfg: dict, metadata_file: dict):
    """
    tests that names in FRONTEND_APP_DEFAULT and metadata provided in app_metadata.json
    corresponds to actual front-end apps produced by static-webserver/client
    """
    frontend_apps_in_repo = {
        feapp["name"] for feapp in client_compile_cfg["applications"]
    }

    frontend_apps_in_metadata = {
        feapp["application"] for feapp in metadata_file["applications"]
    }

    assert (
        frontend_apps_in_repo == frontend_apps_in_metadata
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {metadata_filepath}"

"""
    This tests some invariants considered in the webserver code regarding
    the structure of the frontend apps produced after compiling web/client
"""
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import json
from pathlib import Path
from typing import Dict

import pytest
from simcore_service_webserver.statics_constants import (
    FRONTEND_APP_DEFAULT,
    FRONTEND_APPS_AVAILABLE,
)
from simcore_service_webserver.statics_settings import FrontEndAppSettings

FOGBUGZ_NEWCASE_URL_TEMPLATE = r"https://z43.manuscript.com/f/cases/new?command=new&pg=pgEditBug&ixProject={project}&ixArea={area}"


@pytest.fixture(scope="module")
def client_compile_cfg(web_client_dir: Path) -> Dict:
    compile_filepath = web_client_dir / "compile.json"
    assert compile_filepath.exists()
    cfg = json.loads(compile_filepath.read_text())
    return cfg


@pytest.fixture(scope="module")
def source_boot_index_html(web_client_dir: Path) -> str:
    index_html = web_client_dir / "source" / "boot" / "index.html"
    assert index_html.exists()
    return index_html


def test_expected_frontend_apps_produced_by_webclient(client_compile_cfg: Dict):
    """
    tests that names in FRONTEND_APP_DEFAULT and FRONTEND_APPS_AVAILABLE
    corresponds to actual front-end apps produced by web/client
    """
    frontend_apps_in_repo = {
        feapp["name"] for feapp in client_compile_cfg["applications"]
    }

    product_names = {
        feapp["environment"]["product.name"]
        for feapp in client_compile_cfg["applications"]
    }

    # test FRONTEND_APPS_AVAILABLE
    assert (
        FRONTEND_APPS_AVAILABLE == frontend_apps_in_repo
    ), "Sync with values in FRONTEND_APPS_AVAILABLE with {compile_filepath}"

    assert (
        FRONTEND_APPS_AVAILABLE == frontend_apps_in_repo
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


@pytest.fixture
def test_frontend_app_settings(
    monkeypatch,
):
    monkeypatch.setenv("WEBSERVER_MANUAL_MAIN_URL", "http://some_doc.org")
    monkeypatch.setenv(
        "WEBSERVER_S4L_FOGBUGZ_URL",
        FOGBUGZ_NEWCASE_URL_TEMPLATE.format(project=45, area=458),
    )
    monkeypatch.setenv(
        "WEBSERVER_FOGBUGZ_URL",
        FOGBUGZ_NEWCASE_URL_TEMPLATE.format(project=45, area=457),
    )

    settings = FrontEndAppSettings()

    assert settings.manual_main_url.host == "some_doc.org"
    assert settings.manual_main_url.tld == "org"
    assert str(settings.s4l_fogbugz_newcase_url) == FOGBUGZ_NEWCASE_URL_TEMPLATE.format(
        projet=54, area=458
    )
    assert str(settings.fogbugz_newcase_url) == FOGBUGZ_NEWCASE_URL_TEMPLATE.format(
        project=54, area=457
    )
    assert settings.tis_fogbugz_newcase_url is None

    # is json-serializable
    statics = settings.to_statics()
    assert json.dumps(statics)

    # nulls are not output
    assert "tis_fogbugz_url" not in statics
    assert "fogbugz_url" in statics


def test_default_webserver_env_dev(env_devel_dict):
    assert "WEBSERVER_FOGBUGZ_NEWCASE_URL" in env_devel_dict
    assert env_devel_dict[
        "WEBSERVER_FOGBUGZ_NEWCASE_URL"
    ] == FOGBUGZ_NEWCASE_URL_TEMPLATE.format(project=45, area=449)

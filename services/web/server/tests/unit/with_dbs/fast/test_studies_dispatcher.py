# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
import pytest
from copy import deepcopy
from simcore_service_webserver.log import setup_logging
import logging


@pytest.fixture
def app_cfg(default_app_cfg, aiohttp_unused_port, qx_client_outdir, redis_service):
    """App's configuration used for every test in this module

    NOTE: Overrides services/web/server/tests/unit/with_dbs/conftest.py::app_cfg to influence app setup
    """
    cfg = deepcopy(default_app_cfg)

    cfg["main"]["port"] = aiohttp_unused_port()
    cfg["main"]["client_outdir"] = str(qx_client_outdir)
    cfg["main"]["studies_access_enabled"] = True

    exclude = {
        "tracing",
        "director",
        "smtp",
        "storage",
        "activity",
        "diagnostics",
        "groups",
        "tags",
        "publications",
        "catalog",
        "computation",
    }
    include = {
        "db",
        "rest",
        "projects",
        "login",
        "socketio",
        "resource_manager",
        "users",
        "studies_access",
        "products",
        "studies_dispatcher",
    }

    assert include.intersection(exclude) == set()

    for section in include:
        cfg[section]["enabled"] = True
    for section in exclude:
        cfg[section]["enabled"] = False

    # NOTE: To see logs, use pytest -s --log-cli-level=DEBUG
    setup_logging(level=logging.DEBUG)

    # Enforces smallest GC in the background task
    cfg["resource_manager"]["garbage_collection_interval_seconds"] = 1

    return cfg


# REST-API -------------------------------------------------
#  Samples taken from trials on http://127.0.0.1:9081/dev/doc#/viewer/get_viewer_for_file
#


async def test_api_get_viewer_for_file(client):
    resp = await client.get("/v0/viewers?file_type=DICOM&file_name=foo&file_size=10000")
    assert resp.status_code == 422

    base_url = str(client.app.base_url)
    assert await resp.json() == {
        "data": {
            "file_type": "DICOM",
            "viewer_title": "Sim4life v1.0.16",
            "redirection_url": f"{base_url}/view?file_type=DICOM&file_name=foo&file_size=10000",
        },
        "error": None,
    }


async def test_api_get_viewer_for_unsupported_type(client):
    resp = await client.get("/v0/viewers?file_type=UNSUPPORTED_TYPE")
    assert resp.status_code == 422

    assert await resp.json() == {
        "data": None,
        "error": {
            "logs": [
                {
                    "message": "No viewer available for file type 'UNSUPPORTED_TYPE''",
                    "level": "ERROR",
                    "logger": "user",
                }
            ],
            "errors": [
                {
                    "code": "HTTPUnprocessableEntity",
                    "message": "No viewer available for file type 'UNSUPPORTED_TYPE''",
                    "resource": None,
                    "field": None,
                }
            ],
            "status": 422,
        },
    }


async def test_api_list_supported_filetypes(client):
    resp = await client.get("/v0/viewers/filetypes")

    base_url = str(client.app.base_url)
    assert await resp.json() == {
        "data": [
            {
                "file_type": "DICOM",
                "viewer_title": "Sim4life v1.0.16",
                "redirection_url": f"{base_url}/view?file_type=DICOM",
            },
            {
                "file_type": "CSV",
                "viewer_title": "2d plot - rawgraphs v2.10.6",
                "redirection_url": f"{base_url}/view?file_type=CSV",
            },
        ],
        "error": None,
    }

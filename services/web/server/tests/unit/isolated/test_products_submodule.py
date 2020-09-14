# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import json
from simcore_service_webserver.products import FE_APPS, DEFAULT_FE_APP

def test_frontend_apps_in_sync_with_products(webclient_dir):

    frontend_info = json.loads((webclient_dir / "compile.json").read_text())
    #target = next(
    #    t for t in frontend_info["targets"] if t["type"] == frontend_info["defaultTarget"]
    #)
    #frontend_outdir = webclient_dir / target["outputPath"]


    frontend_apps = [feapp["name"] for feapp in frontend_info["applications"]]
    assert set(frontend_apps) == set(FE_APPS)

    default_frontend_app = next(
        feapp["name"] for feapp in frontend_info["applications"] if feapp["default"]
    )
    assert default_frontend_app == DEFAULT_FE_APP

import uuid as uuidlib

import pytest
from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from simcore_service_webserver.rest import setup_rest
from simcore_service_webserver.share_study import setup_share_study
from utils_assert import assert_status



@pytest.fixture
def client(loop, aiohttp_unused_port, aiohttp_client, api_specs_dir):
    app = web.Application()

    server_kwargs={'port': aiohttp_unused_port(), 'host': 'localhost'}

    # fake config
    app[APP_CONFIG_KEY] = {
        "main": server_kwargs,
        "rest": {
            "version": "v0",
            "location": str(api_specs_dir / "v0" / "openapi.yaml")
        }
    }
    # activates only security+restAPI sub-modules
    #setup_security(app)
    setup_rest(app, debug=True)
    setup_share_study(app)

    cli = loop.run_until_complete( aiohttp_client(app, server_kwargs=server_kwargs) )
    return cli


@pytest.fixture(params=[ str(uuidlib.uuid1()) for _ in range(5)])
async def study_id(request):
    return request.param

#@pytest.mark.parametrize('study_id', [str(uuidlib.uuid1()) for i in range(5)])
async def test_get_shared(client, study_id):
    resp = await client.get(f"/v0/share/study/{study_id}")
    data, _errors = await assert_status(resp, web.HTTPOk)
    assert data.get('copy').endswith(study_id)




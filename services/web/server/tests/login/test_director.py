import pytest
from aiohttp import web

@pytest.fixture()
def director_server(loop, aiohttp_server, app_cfg):
    cfg = app_cfg["storage"]

    app = web.Application()
    async def _get_services(request: web.Request):
        assert not request.has_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"
        return web.json_response({
            'data': [{"user_id": int(query["user_id"])}, ]
        })

    async def _get_running_services(request: web.Request):
        assert not request.has_body

        query = request.query
        assert query
        assert "user_id" in query

        assert query["user_id"], "Expected user id"
        return web.json_response({
            'data': [{"user_id": int(query["user_id"])}, ]
        })


    app.router.add_get("/v0/locations", _get_locs)
    app.router.add_get("/v0/locations/0/files/{file_id}", _get_dlink)

    assert cfg['host']=='localhost'

    server = loop.run_until_complete(aiohttp_server(app, port= cfg['port']))
    return server
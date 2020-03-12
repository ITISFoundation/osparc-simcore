# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import copy

from aiohttp import web

from servicelib.openapi_aiohttp_request import AiohttpOpenAPIRequestFactory
from servicelib.openapi_aiohttp_response import AiohttpOpenAPIResponseFactory

import pytest
from yarl import URL


# FIXME: <-----------

@pytest.mark.parametrize(
    "path,path_values",
    [
        (r"/my/tokens/{service}", {"service": "foo"}),
        (r"/my/tokens/{service:google|facebook}/", {"service": "google"}),
        (r"/my/tokens/{identifier:\d+}/", {"identifier": 22}),
    ],
)
async def test_openapi_aiohttp_adapters(path, path_values, aiohttp_client, loop):
    # data used in both request and response
    query_values = {
        "int": 1,
        "string": "string",
    }  # NOTE: values can ONLY be ints or str

    data = {"int": 1, "string": "string", "bool": True}
    data["json"] = copy.deepcopy(data)

    # tests request
    async def hello(request: web.Request):
        return web.Response(text="Hello, world")

    async def _handler(request: web.Request):

        try:
            oac_request = await AiohttpOpenAPIRequestFactory.create(request)

            assert oac_request.method == "post"
            assert oac_request.body == data
            assert oac_request.mimetype == "application/json"
            assert oac_request.parameters.path == path_values
            assert oac_request.parameters.query == query_values
            assert oac_request.parameters.header == {}
            assert oac_request.parameters.cookie == {}
            assert oac_request.full_url_pattern == str(request.origin().with_path(path))

        except AssertionError as err:
            # TODO:
            raise web.HTTPServerError(reason=str(err))
            ## import pdb; pdb.set_trace()

        return web.json_response(data, status=201)

    app = web.Application()
    app.router.add_get("/", hello)
    app.router.add_post(path, _handler, name="test-path")

    print([r for r in app.router.resources()])

    # tests responses
    client = await aiohttp_client(app)

    resp: web.Response = await client.get("/")
    oas_response = AiohttpOpenAPIResponseFactory.create(resp)

    assert oas_response.status_code == 200
    assert oas_response.data == "Hello, world"
    assert oas_response.mimetype == "application/text"

    resp: web.Response = await client.post(
        app.router["test-path"].url_for(**path_values), #.with_query(**query_values),
        json=data,
    )
    oas_response = AiohttpOpenAPIResponseFactory.create(resp)

    assert oas_response.status_code == 201
    assert oas_response.data == data
    assert oas_response.mimetype == "application/json"

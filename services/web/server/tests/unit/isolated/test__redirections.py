# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import textwrap
from pathlib import Path

import pytest
from aiohttp import web


@pytest.fixture
def index_static_path(tmpdir):
    statics_dir = tmpdir.mkdir("statics")

    index_file = Path(statics_dir.join("index.html"))
    index_file.write_text(
        textwrap.dedent(
            """\
    <!DOCTYPE html>
    <html>
        <body>
            <h1>My First Heading</h1>
            <p>My first paragraph.</p>
        </body>
    </html>
    """
        )
    )

    return statics_dir


@pytest.fixture
def client(loop, aiohttp_client, index_static_path):

    routes = web.RouteTableDef()

    @routes.get("/")
    async def get_root(_request):
        raise web.HTTPOk()

    @routes.get("/other")
    async def get_other(_request):
        raise web.HTTPOk()

    @routes.get("/redirect-to-other")
    async def get_redirect_to_other(request):
        raise web.HTTPFound("/other")

    @routes.get("/redirect-to-static")
    async def get_redirect_to_static(_request):
        raise web.HTTPFound("/statics/index.html")

    @routes.get("/redirect-to-root")
    async def get_redirect_to_root(_request):
        raise web.HTTPFound("/")

    routes.static("/statics", index_static_path)

    app = web.Application()
    app.add_routes(routes)
    cli = loop.run_until_complete(aiohttp_client(app))
    return cli


@pytest.mark.parametrize("test_path", ["/", "/other"])
async def test_preserves_fragments(client, test_path):
    resp = await client.get(f"{test_path}#this/is/a/fragment")
    assert resp.real_url.path == test_path
    assert resp.real_url.fragment == "this/is/a/fragment"


@pytest.mark.xfail
@pytest.mark.parametrize(
    "test_path,expected_redirected_path",
    [
        ("/redirect-to-other", "/other"),
        ("/redirect-to-root", "/"),
        ("/redirect-to-static", "/statics/index.html"),
    ],
)
async def test_redirects_and_fragments(client, test_path, expected_redirected_path):
    resp = await client.get(f"{test_path}#this/is/a/fragment")
    assert resp.real_url.path == f"{expected_redirected_path}"

    # HOW TO PRESERVE FRAGMENTS IN A REDIRECTION <------???
    assert resp.real_url.fragment == "this/is/a/fragment"

    #
    #  /study/123  --> redirect to /#study/123
    #  /#study/123 --> / --> redirect to /osparc/index.html
    #  /osparc/index.html AND we have lost #!?
    #

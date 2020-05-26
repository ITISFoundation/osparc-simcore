""" Reverse-proxy customized for paraview

    Differences with the generic reverse proxy are that when returning Visualizer.js,
    the path included to the websocket endpoint is set as follows:
    ws://hostname+port+"/ws" which must be changed to ws://hostname+port+"x/node_uuid/ws". This allows
    us to recognize the connection when the client tries to connect.

    Also, when connecting the websocket, it needs to be set back to what paraview server expects, thus ws://hostname+port/ws.

"""

import asyncio
import logging
import pprint

import aiohttp
from aiohttp import client, web
from yarl import URL

from ..settings import APP_SOCKETS_KEY

SUPPORTED_IMAGE_NAME = [
    "simcore/services/dynamic/3d-viewer",
    "simcore/services/dynamic/3d-viewer-gpu",
]
SUPPORTED_IMAGE_TAG = "==1.0.5"

logger = logging.getLogger(__name__)


def check_ws_in_headers(request):
    return (
        request.headers.get("connection", "").lower() == "upgrade"
        and request.headers.get("upgrade", "").lower() == "websocket"
        and request.method == "GET"
    )


async def handle_websocket_requests(ws_server, request: web.Request, target_url: URL):
    async def _ws_forward(ws_from, ws_to):
        async for msg in ws_from:
            mt = msg.type
            md = msg.data
            if mt == aiohttp.WSMsgType.TEXT:
                await ws_to.send_str(md)
            elif mt == aiohttp.WSMsgType.BINARY:
                await ws_to.send_bytes(md)
            elif mt == aiohttp.WSMsgType.PING:
                await ws_to.ping()
            elif mt == aiohttp.WSMsgType.PONG:
                await ws_to.pong()
            elif ws_to.closed:
                await ws_to.close(code=ws_to.close_code, message=msg.extra)
            else:
                raise ValueError("unexpected message type: %s" % pprint.pformat(msg))

    async with aiohttp.ClientSession(cookies=request.cookies) as session:
        # websocket connection with backend services
        async with session.ws_connect(target_url) as ws_client:
            await asyncio.wait(
                [_ws_forward(ws_server, ws_client), _ws_forward(ws_client, ws_server)],
                return_when=asyncio.FIRST_COMPLETED,
            )

            return ws_server


async def handle_web_request(
    request: web.Request, target_url: URL, mount_point: str, proxy_path: str
):
    async with client.request(
        request.method,
        target_url,
        headers=request.headers.copy(),
        allow_redirects=False,
        data=await request.read(),
    ) as res:
        # special handling for paraview
        headers = res.headers.copy()
        del headers["content-length"]
        body = await res.read()
        if proxy_path == "Visualizer.js":
            body = body.replace(
                b'"https"===window.location.protocol',
                b'window.location.protocol.startsWith("https")',
            )
            body = body.replace(b'"/ws"', b'"%s/ws"' % mount_point.encode(), 1)
            body = body.replace(
                b'"/paraview/"', b'"%s/paraview/"' % mount_point.encode(), 1
            )
            logger.info("fixed Visualizer.js paths on the fly")
        response = web.Response(headers=headers, status=res.status, body=body)
        return response


async def handler(
    request: web.Request, service_url: str, mount_point: str, proxy_path: str, **_kargs
):
    logger.debug("handling request %s, using service url %s", request, service_url)
    target_url = (
        URL(service_url).origin().with_path(request.path).with_query(request.query)
    )
    ws_available = False
    if check_ws_in_headers(request):
        ws = web.WebSocketResponse()
        ws_available = ws.can_prepare(request)
        if ws_available:
            await ws.prepare(request)
            logger.info("##### WS_SERVER %s", pprint.pformat(ws))
            try:
                request.app[APP_SOCKETS_KEY].append(ws)
                # paraview special handling, it is somehow fixed at the root endpoint
                ws_url = URL(service_url).with_path("ws")
                ws = await handle_websocket_requests(ws, request, ws_url)
                return ws
            finally:
                request.app[APP_SOCKETS_KEY].remove(ws)
    if not ws_available:
        return await handle_web_request(request, target_url, mount_point, proxy_path)


if __name__ == "__main__":
    # dummies for manual testing
    BASE_URL = "http://0.0.0.0:8080"
    MOUNT_POINT = "/x/fakeUuid"

    def adapter(req: web.Request):
        proxy_path = req.match_info.get("proxyPath", "no proxyPath placeholder defined")
        return handler(req, BASE_URL, MOUNT_POINT, proxy_path)

    app = web.Application()
    app.router.add_route("*", MOUNT_POINT + "{proxyPath:.*}", adapter)
    web.run_app(app, port=3985)

""" Default implementation of reverse-proxy

TODO: https://stackoverflow.com/questions/46788964/trying-to-build-a-proxy-with-aiohttp
TODO: https://github.com/weargoggles/aioproxy/blob/master/aioproxy.py

- another possibility: always request director and thisone will redirect to real server...
  CONS: will double #calls
  PROS: location of the dyb service can change at will!
"""
import asyncio
import logging
import pprint
import time

import aiohttp
from aiohttp import client, web
from yarl import URL

from ..settings import APP_SOCKETS_KEY

logger = logging.getLogger(__name__)

CHUNK = 32768


def check_ws_in_headers(request):
    return (
        request.headers.get("connection", "").lower() == "upgrade"
        and request.headers.get("upgrade", "").lower() == "websocket"
        and request.method == "GET"
    )


async def handle_websocket_requests(ws_server, request, target_url):
    client_session = aiohttp.ClientSession(cookies=request.cookies)

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

    async with client_session.ws_connect(target_url) as ws_client:
        await asyncio.wait(
            [_ws_forward(ws_server, ws_client), _ws_forward(ws_client, ws_server)],
            return_when=asyncio.FIRST_COMPLETED,
        )

        return ws_server


async def handle_web_request(request, target_url):
    async with client.request(
        request.method,
        target_url,
        headers=request.headers.copy(),
        allow_redirects=False,
        data=await request.read(),
    ) as res:
        body = await res.read()
        response = web.Response(
            headers=res.headers.copy(), status=res.status, body=body
        )
        return response


async def handler(request: web.Request, service_url: str, **_kargs):
    target_url = (
        URL(service_url).origin().with_path(request.path).with_query(request.query)
    )
    ws_available = False
    if check_ws_in_headers(request):
        ws = web.WebSocketResponse()
        ws_available = ws.can_prepare(request)
        if ws_available:
            await ws.prepare(request)
            try:
                request.app[APP_SOCKETS_KEY].append(ws)

                ws = await handle_websocket_requests(ws, request, target_url)
                return ws
            finally:
                request.app[APP_SOCKETS_KEY].remove(ws)

    if not ws_available:
        return await handle_web_request(request, target_url)


# OTHER IMPLEMENTATIONS ------------------------------------------------------


async def handler_impl_2(request: web.Request, target_url: str):
    # FIXME: Taken tmp from https://github.com/weargoggles/aioproxy/blob/master/aioproxy.py

    start = time.time()
    async with aiohttp.client.request(
        request.method,
        target_url,
        headers=request.headers,
        chunked=CHUNK,
        # response_class=ReverseProxyResponse,
    ) as r:
        logger.debug("opened backend request in %d ms", ((time.time() - start) * 1000))

        response = aiohttp.web.StreamResponse(status=r.status, headers=r.headers)
        await response.prepare(request)
        content = r.content
        while True:
            chunk = await content.read(CHUNK)
            if not chunk:
                break
            await response.write(chunk)

    logger.debug("finished sending content in %d ms", ((time.time() - start) * 1000,))
    await response.write_eof()
    return response

    # except web.HttpStatus as status:
    #    return status.as_response()

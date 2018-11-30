""" Default implementation of reverse-proxy

TODO: https://stackoverflow.com/questions/46788964/trying-to-build-a-proxy-with-aiohttp
TODO: https://github.com/weargoggles/aioproxy/blob/master/aioproxy.py

- another possibility: always request director and thisone will redirect to real server...
  CONS: will double #calls
  PROS: location of the dyb service can change at will!
"""
import logging
import time
import asyncio

import aiohttp
from aiohttp import web, client

from yarl import URL
import pprint


logger = logging.getLogger(__name__)

CHUNK = 32768


async def handler(request: web.Request, service_url: str, **_kargs):
    try:
        target_url = URL(service_url).origin().with_path(request.path).with_query(request.query)
        res = await handler_impl_1(request, target_url)
        return res
    except web.HTTPError as err:
        logger.debug("reverse proxy %s", request, exec_info=err)
        raise web.HTTPServiceUnavailable(reason="Cannot talk to spawner",
                                         content_type="application/json")

# IMPLEMENTATIONS ---------------------------------------------------------------------
def is_ws(request):
    return request.headers.get('connection') == 'Upgrade' and \
           request.headers.get('upgrade') == 'websocket' and \
           request.method == 'GET'

async def ws_forward(ws_from, ws_to):
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
            raise ValueError(
                'unexpected message type: %s' % pprint.pformat(msg))


async def handle_websockets(request, target_url):
    server_res = web.WebSocketResponse()
    await server_res.prepare(request)

    client_session = aiohttp.ClientSession(cookies=request.cookies)
    async with client_session.ws_connect(target_url) as client_res:
        await asyncio.wait([ws_forward(server_res, client_res),
                            ws_forward(client_res, server_res)],
                            return_when=asyncio.FIRST_COMPLETED)

        return server_res



async def handler_impl_1(request: web.Request, target_url: str):
    reqH = request.headers.copy()

    if is_ws(request):
        response = await handle_websockets(request, target_url)
    else:
        async with client.request(
            request.method, target_url,
            headers=reqH,
            allow_redirects=False,
            data=await request.read()
        ) as res:
            body = await res.read()
            response = web.Response(
                headers=res.headers.copy(),
                status=res.status,
                body=body
            )
            return response






async def handler_impl_2(request: web.Request, target_url: str):
    # FIXME: Taken tmp from https://github.com/weargoggles/aioproxy/blob/master/aioproxy.py

    start = time.time()
    async with aiohttp.client.request(
        request.method, target_url,
        headers=request.headers,
        chunked=CHUNK,
        # response_class=ReverseProxyResponse,
    ) as r:
        logger.debug('opened backend request in %d ms', ((time.time() - start) * 1000))

        response = aiohttp.web.StreamResponse(status=r.status,
                                                headers=r.headers)
        await response.prepare(request)
        content = r.content
        while True:
            chunk = await content.read(CHUNK)
            if not chunk:
                break
            await response.write(chunk)

    logger.debug('finished sending content in %d ms', ((time.time() - start) * 1000,))
    await response.write_eof()
    return response

    # except web.HttpStatus as status:
    #    return status.as_response()

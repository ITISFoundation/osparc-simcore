import asyncio
import logging
import pprint

import aiohttp
from aiohttp import client, web

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


baseUrl = 'http://0.0.0.0:8080'
mountPoint = '/fakeUuid'


async def handler(req):
    proxyPath = req.match_info.get(
        'proxyPath', 'no proxyPath placeholder defined')
    reqH = req.headers.copy()
    if reqH['connection'] == 'Upgrade' and reqH['upgrade'] == 'websocket' and req.method == 'GET':

        ws_server = web.WebSocketResponse()
        await ws_server.prepare(req)
        logger.info('##### WS_SERVER %s', pprint.pformat(ws_server))

        client_session = aiohttp.ClientSession(cookies=req.cookies)
        async with client_session.ws_connect(
            baseUrl+proxyPath,
        ) as ws_client:
            logger.info('##### WS_CLIENT %s', pprint.pformat(ws_client))

            async def ws_forward(ws_from, ws_to):
                async for msg in ws_from:
                    #logger.info('>>> msg: %s',pprint.pformat(msg))
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

            await asyncio.wait([ws_forward(ws_server, ws_client), ws_forward(ws_client, ws_server)], return_when=asyncio.FIRST_COMPLETED)

            return ws_server
    else:
        async with client.request(
            req.method, baseUrl+proxyPath,
            headers=reqH,
            allow_redirects=False,
            data=await req.read()
        ) as res:
            headers = res.headers.copy()
            del headers['content-length']
            body = await res.read()
            if proxyPath == '/Visualizer.js':
                body = body.replace(b'"/ws"', b'"%s/ws"' %
                                    mountPoint.encode(), 1)
                body = body.replace(
                    b'"/paraview/"', b'"%s/paraview/"' % mountPoint.encode(), 1)
                logger.info("fixed Visualizer.js paths on the fly")
            return web.Response(
                headers=headers,
                status=res.status,
                body=body
            )
        return ws_server

app = web.Application()
app.router.add_route('*', mountPoint + '{proxyPath:.*}', handler)
web.run_app(app, port=3985)

""" Reverse-proxy customized for jupyter notebooks

"""

import asyncio
import logging
import pprint

import aiohttp
from aiohttp import client, web
from yarl import URL

#FIXME: make this more generic
SUPPORTED_IMAGE_NAME = ["simcore/services/dynamic/jupyter-base-notebook",
                        "simcore/services/dynamic/jupyter-scipy-notebook"
                        "simcore/services/dynamic/kember-viewer", 
                        "simcore/services/dynamic/cc-2d-viewer", 
                        "simcore/services/dynamic/cc-1d-viewer", 
                        "simcore/services/dynamic/cc-0d-viewer"]
SUPPORTED_IMAGE_TAG = ">=1.5.0"

logger = logging.getLogger(__name__)


async def handler(req: web.Request, service_url: str, **_kwargs):
    """ Redirects communication to jupyter notebook in the backend

    :param req: aiohttp request
    :type req: web.Request
    :param service_url: Resolved url pointing to backend jupyter service. Typically http:hostname:port/x/12345/.
    :type service_url: str
    :raises ValueError: Unexpected web-socket message
    """

    # FIXME: hash of statics somehow get do not work. then neeed to be strip away
    # Removing query ... which not sure is a good idea
    target_url = URL(service_url).origin() / req.path.lstrip('/')

    reqH = req.headers.copy()

    if reqH.get('connection', '').lower() == 'upgrade' and reqH.get('upgrade', '').lower() == 'websocket' and req.method == 'GET':
        ws_server = web.WebSocketResponse()
        await ws_server.prepare(req)
        logger.info('##### WS_SERVER %s', pprint.pformat(ws_server))

        client_session = aiohttp.ClientSession(cookies=req.cookies)
        async with client_session.ws_connect(target_url) as ws_client:
            logger.info('##### WS_CLIENT %s', pprint.pformat(ws_client))

            async def ws_forward(ws_from, ws_to):
                async for msg in ws_from:
                    logger.debug('>>> msg: %s', pprint.pformat(msg))
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
            req.method, target_url,
            headers=reqH,
            allow_redirects=False,
            data=await req.read()
        ) as res:
            body = await res.read()
            response = web.Response(
                headers=res.headers.copy(),
                status=res.status,
                body=body
            )
            return response


if __name__ == "__main__":
    # dummies for manual testing
    BASE_URL = 'http://0.0.0.0:8888'
    MOUNT_POINT = '/x/12345'

    def adapter(req: web.Request):
        return handler(req, service_url=BASE_URL)

    app = web.Application()
    app.router.add_route('*', MOUNT_POINT + '/{proxyPath:.*}', adapter)
    web.run_app(app, port=3984)

""" Default implementation of reverse-proxy

TODO: https://stackoverflow.com/questions/46788964/trying-to-build-a-proxy-with-aiohttp
TODO: https://github.com/weargoggles/aioproxy/blob/master/aioproxy.py

- another possibility: always request director and thisone will redirect to real server...
  CONS: will double #calls
  PROS: location of the dyb service can change at will!
"""
import logging
import time

import aiohttp
from aiohttp import web

from yarl import URL
logger = logging.getLogger(__name__)


CHUNK = 32768


async def handler(request: web.Request, service_url: str, **_kwargs) -> web.StreamResponse:
    # FIXME: Taken tmp from https://github.com/weargoggles/aioproxy/blob/master/aioproxy.py
    start = time.time()
    try:
        # FIXME: service_url should be service_endpoint or service_origins
        target_url = URL(service_url).origin().with_path(request.path).with_query(request.query)

        async with aiohttp.client.request(
            request.method, target_url,
            headers=request.headers,
            chunked=CHUNK,
            # response_class=ReverseProxyResponse,
        ) as r:
            logger.debug('opened backend request in %d ms',
                         ((time.time() - start) * 1000))
            response = aiohttp.web.StreamResponse(status=r.status,
                                                  headers=r.headers)
            await response.prepare(request)
            content = r.content
            while True:
                chunk = await content.read(CHUNK)
                if not chunk:
                    break
                await response.write(chunk)

        logger.debug('finished sending content in %d ms',
                     ((time.time() - start) * 1000,))
        await response.write_eof()
        return response
    except Exception:
        logger.debug("reverse proxy %s", request, exec_info=True)
        raise web.HTTPServiceUnavailable(reason="Cannot talk to spawner",
                                         content_type="application/json")

    # except web.HttpStatus as status:
    #    return status.as_response()

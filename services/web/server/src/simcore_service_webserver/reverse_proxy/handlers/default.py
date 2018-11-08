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

logger = logging.getLogger(__name__)


CHUNK = 32768


async def handler(self, request):
    # FIXME: Taken tmp from https://github.com/weargoggles/aioproxy/blob/master/aioproxy.py
    start = time.time()
    try:
        host, port = await self.get_destination_details(request)
        host_and_port = "%s:%d" % (host, port)

        async with aiohttp.client.request(
            request.method, 'http://' + host_and_port + request.path,
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
                response.write(chunk)

        logger.debug('finished sending content in %d ms',
                    ((time.time() - start) * 1000,))
        await response.write_eof()
        return response
    except Exception:
        raise web.HTTPServiceUnavailable(reason="Cannot talk to spawner",
                                    content_type="application/json")

    #except web.HttpStatus as status:
    #    return status.as_response()

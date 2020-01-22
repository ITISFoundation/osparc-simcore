from functools import wraps
from typing import Any, Dict, Tuple

from aiohttp import web
from yarl import URL

from simcore_service_director import config


def cache_requests(http_request: Any):
    @wraps(http_request)
    async def wrapped(app: web.Application, url: URL, method: str ="GET") -> Tuple[Dict, Dict]:
        if config.REGISTRY_CACHING:
            cache_data = app[config.APP_REGISTRY_CACHE_DATA_KEY]
            cache_key = "{}_{}".format(url, method)
            if cache_key in cache_data:
                return cache_data[cache_key]

        resp_data, resp_headers = await http_request(app, url, method)

        if config.REGISTRY_CACHING:
            cache_data[cache_key] = (resp_data, resp_headers)
        
        return (resp_data, resp_headers)
            
    return wrapped

__all__ = [
    "cache_requests"
]

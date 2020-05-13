from functools import wraps
from typing import Coroutine, Dict, Tuple

from aiohttp import web

from simcore_service_director import config


def cache_requests(func: Coroutine, no_cache: bool = False):
    @wraps(func)
    async def wrapped(
        app: web.Application, url: str, method: str, *args, **kwargs
    ) -> Tuple[Dict, Dict]:
        is_cache_enabled = config.DIRECTOR_REGISTRY_CACHING and method == "GET"
        cache_key = f"{url}:{method}"
        if is_cache_enabled and not no_cache:
            cache_data = app[config.APP_REGISTRY_CACHE_DATA_KEY]
            if cache_key in cache_data:
                return cache_data[cache_key]

        resp_data, resp_headers = await func(app, url, method, *args, **kwargs)

        if is_cache_enabled:
            cache_data = app[config.APP_REGISTRY_CACHE_DATA_KEY]
            cache_data[cache_key] = (resp_data, resp_headers)

        return (resp_data, resp_headers)

    return wrapped


__all__ = ["cache_requests"]

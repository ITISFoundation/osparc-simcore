from functools import wraps
from typing import Coroutine

from fastapi import FastAPI
from simcore_service_director import config


def cache_requests(func: Coroutine, *, no_cache: bool = False):
    @wraps(func)
    async def wrapped(
        app: FastAPI, url: str, method: str, *args, **kwargs
    ) -> tuple[dict, dict]:
        is_cache_enabled = config.DIRECTOR_REGISTRY_CACHING and method == "GET"
        cache_key = f"{url}:{method}"
        if is_cache_enabled and not no_cache:
            cache_data = app.state.registry_cache
            if cache_key in cache_data:
                return cache_data[cache_key]

        resp_data, resp_headers = await func(app, url, method, *args, **kwargs)

        if is_cache_enabled and not no_cache:
            cache_data = app.state.registry_cache
            cache_data[cache_key] = (resp_data, resp_headers)

        return (resp_data, resp_headers)

    return wrapped


__all__ = ["cache_requests"]

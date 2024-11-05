from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any

from fastapi import FastAPI

from .core.settings import get_application_settings


def cache_requests(
    func: Callable[..., Awaitable[tuple[dict[str, Any], dict[str, Any]]]],
    *,
    no_cache: bool = False,
) -> Callable[..., Awaitable[tuple[dict[str, Any], dict[str, Any]]]]:
    @wraps(func)
    async def wrapped(
        app: FastAPI, url: str, method: str, *args, **kwargs
    ) -> tuple[dict, dict]:
        app_settings = get_application_settings(app)
        is_cache_enabled = app_settings.DIRECTOR_REGISTRY_CACHING and method == "GET"
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

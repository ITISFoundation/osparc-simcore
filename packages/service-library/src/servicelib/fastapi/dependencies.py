""" Common utils for api/dependencies
"""

from typing import Any, Callable

from fastapi import FastAPI, Request


def get_app(request: Request) -> FastAPI:
    return request.app


def get_reverse_url_mapper(request: Request) -> Callable[..., str]:
    def _url_for(name: str, **path_params: Any) -> str:
        # Analogous to https://docs.aiohttp.org/en/stable/web_quickstart.html#reverse-url-constructing-using-named-resources
        url: str = f"{request.url_for(name, **path_params)}"
        return url

    return _url_for

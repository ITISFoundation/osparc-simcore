from typing import Any, Callable, cast

from fastapi import Request


def get_reverse_url_mapper(request: Request) -> Callable[..., str]:
    def reverse_url_mapper(name: str, **path_params: Any) -> str:
        # NOTE: the cast appears to be needed by mypy
        return cast(str, request.url_for(name, **path_params))

    return reverse_url_mapper

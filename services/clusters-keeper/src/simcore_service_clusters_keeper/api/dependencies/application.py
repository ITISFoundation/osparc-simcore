from typing import cast

from fastapi import FastAPI, Request


def get_app(request: Request) -> FastAPI:
    return cast(FastAPI, request.app)

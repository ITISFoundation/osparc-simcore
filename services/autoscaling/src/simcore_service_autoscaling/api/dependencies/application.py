from fastapi import FastAPI, Request


def get_app(request: Request) -> FastAPI:
    return request.app

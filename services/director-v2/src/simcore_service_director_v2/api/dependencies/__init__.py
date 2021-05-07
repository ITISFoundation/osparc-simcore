from fastapi import Request, FastAPI


def get_app(request: Request) -> FastAPI:
    return request.app

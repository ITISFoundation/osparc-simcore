"""Generate an OpenAPI spec containing only endpoints tagged as openai-compatible."""

import json

from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi
from fastapi.routing import APIRoute
from simcore_service_api_server._meta import API_VERSION, API_VTAG, APP_NAME
from simcore_service_api_server.api.routes import responses as _responses


def _is_openai_compatible(route) -> bool:
    if isinstance(route, APIRoute):
        extra = route.openapi_extra or {}
        return extra.get("x-openai-compatible", False)
    return False


def main() -> None:
    app = FastAPI(title=APP_NAME, version=API_VERSION)
    router = APIRouter()
    router.include_router(_responses.router, tags=["responses"], prefix="/responses")
    app.include_router(router, prefix=f"/{API_VTAG}")

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        routes=[route for route in app.routes if _is_openai_compatible(route)],
    )

    # Remove the x-openai-compatible extension from the generated spec
    for methods in openapi_schema.get("paths", {}).values():
        for operation in methods.values():
            if isinstance(operation, dict):
                operation.pop("x-openai-compatible", None)

    print(json.dumps(openapi_schema, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()

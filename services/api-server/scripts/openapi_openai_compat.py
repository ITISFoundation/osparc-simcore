"""Generate an OpenAPI spec containing only endpoints tagged as openai-compatible."""

import json

from fastapi import APIRouter, FastAPI
from fastapi.openapi.utils import get_openapi
from simcore_service_api_server._meta import API_VERSION, API_VTAG, APP_NAME
from simcore_service_api_server.api.routes import responses as _responses
from simcore_service_api_server.api.routes._constants import OPENAI_COMPATIBLE_TAG


def main() -> None:
    app = FastAPI(title=APP_NAME, version=API_VERSION)
    router = APIRouter()
    router.include_router(_responses.router, tags=["responses"], prefix="/responses")
    app.include_router(router, prefix=f"/{API_VTAG}")

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        routes=[route for route in app.routes if OPENAI_COMPATIBLE_TAG in getattr(route, "tags", [])],
    )

    print(json.dumps(openapi_schema, indent=2))  # noqa: T201


if __name__ == "__main__":
    main()

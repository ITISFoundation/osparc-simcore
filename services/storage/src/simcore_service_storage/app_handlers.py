"""

    - Checks connectivity with other services in the backend

"""
from aiohttp.web import Request, RouteTableDef
from models_library.app_diagnostics import AppStatusCheck

from .db import get_engine_state
from .db import is_service_responsive as is_pg_responsive
from .meta import api_version, api_version_prefix, app_name

routes = RouteTableDef()


@routes.get(f"/{api_version_prefix}/status")
async def get_app_status(request: Request):
    # NOTE: all calls here must NOT raise

    status = AppStatusCheck.parse_obj(
        {
            "app_name": app_name,
            "version": api_version,
            "services": {
                "postgres": {
                    "healthy": await is_pg_responsive(request.app),
                    "pool": get_engine_state(request.app),
                },
                # TODO: s3-minio
            },
        }
    )

    return status.dict(exclude_unset=True)

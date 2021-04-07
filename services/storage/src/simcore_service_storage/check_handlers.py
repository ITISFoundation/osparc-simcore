"""

    - Checks connectivity with other services in the backend

"""
from aiohttp.web import Request, RouteTableDef

from .db import get_engine_state
from .db import is_service_responsive as is_pg_responsive
from .meta import api_version, api_version_prefix, app_name

# TODO: from .s3 import is_s3_responsive

VX = f"/{api_version_prefix}"

routes = RouteTableDef()


@routes.get(VX + "/check")
async def check_status(request: Request):
    # NOTE: all calls here must NOT raise

    return {
        "name": app_name,
        "version": api_version,
        "postgres": {
            "pool": get_engine_state(request.app),
            "responsive": await is_pg_responsive(request.app),
        },
        # "s3": {
        #     "responsive": await is_s3_responsive(request.app)
        # }
    }

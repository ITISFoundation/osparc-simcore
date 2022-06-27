"""

    - Checks connectivity with other services in the backend

"""
import logging

from aiohttp.web import Request, RouteTableDef
from models_library.api_schemas_storage import HealthCheck
from models_library.app_diagnostics import AppStatusCheck
from servicelib.aiohttp.rest_utils import extract_and_validate

from ._meta import api_version, api_version_prefix, app_name
from .db import get_engine_state
from .db import is_service_responsive as is_pg_responsive

log = logging.getLogger(__name__)

routes = RouteTableDef()


@routes.get(f"/{api_version_prefix}/", name="health_check")  # type: ignore
async def get_health(request: Request):
    """Service health-check endpoint
    Some general information on the API and state of the service behind
    """
    log.debug("CHECK HEALTH INCOMING PATH %s", request.path)
    await extract_and_validate(request)

    return HealthCheck.parse_obj(
        {"name": app_name, "version": api_version, "api_version": api_version}
    ).dict(exclude_unset=True)


@routes.get(f"/{api_version_prefix}/status", name="get_status")  # type: ignore
async def get_status(request: Request):
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
                "s3": {"healthy": True},
            },
        }
    )

    return status.dict(exclude_unset=True)

"""

    - Checks connectivity with other services in the backend

"""
import logging

from aiohttp import web
from aws_library.s3.errors import S3AccessError, S3BucketInvalidError
from models_library.api_schemas_storage import HealthCheck, S3BucketName
from models_library.app_diagnostics import AppStatusCheck
from servicelib.json_serialization import json_dumps
from servicelib.rest_constants import RESPONSE_MODEL_POLICY

from ._meta import API_VERSION, API_VTAG, PROJECT_NAME, VERSION
from .constants import APP_CONFIG_KEY
from .db import get_engine_state
from .db import is_service_responsive as is_pg_responsive
from .s3 import get_s3_client
from .settings import Settings

log = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/", name="health_check")
async def get_health(request: web.Request) -> web.Response:
    assert request  # nosec
    return web.json_response(
        {
            "data": HealthCheck.parse_obj(
                {
                    "name": PROJECT_NAME,
                    "version": f"{VERSION}",
                    "api_version": API_VERSION,
                }
            ).dict(**RESPONSE_MODEL_POLICY)
        },
        dumps=json_dumps,
    )


@routes.get(f"/{API_VTAG}/status", name="get_status")
async def get_status(request: web.Request) -> web.Response:
    # NOTE: all calls here must NOT raise
    assert request.app  # nosec
    app_settings: Settings = request.app[APP_CONFIG_KEY]
    s3_state = "disabled"
    if app_settings.STORAGE_S3:
        try:
            await get_s3_client(request.app).check_bucket_connection(
                S3BucketName(app_settings.STORAGE_S3.S3_BUCKET_NAME)
            )
            s3_state = "connected"
        except S3BucketInvalidError:
            s3_state = "no access to S3 bucket"
        except S3AccessError:
            s3_state = "failed"

    postgres_state = "disabled"
    if app_settings.STORAGE_POSTGRES:
        postgres_state = (
            "connected" if await is_pg_responsive(request.app) else "failed"
        )

    status = AppStatusCheck.parse_obj(
        {
            "app_name": PROJECT_NAME,
            "version": f"{VERSION}",
            "services": {
                "postgres": {
                    "healthy": postgres_state,
                    "pool": get_engine_state(request.app),
                },
                "s3": {"healthy": s3_state},
            },
        }
    )

    return web.json_response(
        {"data": status.dict(exclude_unset=True)}, dumps=json_dumps
    )

"""

- Checks connectivity with other services in the backend

"""

import logging

from aiohttp import web
from aws_library.s3 import S3AccessError
from common_library.json_serialization import json_dumps
from fastapi import Request
from models_library.api_schemas_storage import HealthCheck, S3BucketName
from models_library.app_diagnostics import AppStatusCheck
from pydantic import TypeAdapter
from servicelib.db_asyncpg_utils import check_postgres_liveness
from servicelib.fastapi.db_asyncpg_engine import get_engine
from servicelib.rest_constants import RESPONSE_MODEL_POLICY
from simcore_postgres_database.utils_aiosqlalchemy import get_pg_engine_stateinfo

from ..._meta import API_VERSION, API_VTAG, PROJECT_NAME, VERSION
from ...core.settings import get_application_settings
from ...modules.s3 import get_s3_client

_logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get(f"/{API_VTAG}/", name="health_check")
async def get_health(request: web.Request) -> web.Response:
    assert request  # nosec
    return web.json_response(
        {
            "data": HealthCheck(
                name=PROJECT_NAME,
                version=f"{VERSION}",
                api_version=API_VERSION,
                status=None,
            ).model_dump(**RESPONSE_MODEL_POLICY)
        },
        dumps=json_dumps,
    )


@routes.get(f"/{API_VTAG}/status", name="get_status")
async def get_status(request: Request) -> web.Response:
    # NOTE: all calls here must NOT raise
    assert request.app  # nosec
    app_settings = get_application_settings(request.app)
    s3_state = "disabled"
    if app_settings.STORAGE_S3:
        try:
            s3_state = (
                "connected"
                if await get_s3_client(request.app).bucket_exists(
                    bucket=TypeAdapter(S3BucketName).validate_python(
                        app_settings.STORAGE_S3.S3_BUCKET_NAME
                    )
                )
                else "no access to S3 bucket"
            )
        except S3AccessError:
            s3_state = "failed"

    postgres_state = "disabled"

    if app_settings.STORAGE_POSTGRES:
        postgres_state = (
            "connected"
            if await check_postgres_liveness(get_engine(request.app))
            else "failed"
        )

    status = AppStatusCheck.model_validate(
        {
            "app_name": PROJECT_NAME,
            "version": f"{VERSION}",
            "services": {
                "postgres": {
                    "healthy": postgres_state,
                    "pool": get_pg_engine_stateinfo(get_engine(request.app)),
                },
                "s3": {"healthy": s3_state},
            },
        }
    )

    return web.json_response(
        {"data": status.model_dump(exclude_unset=True)}, dumps=json_dumps
    )

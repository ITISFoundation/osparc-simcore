"""

- Checks connectivity with other services in the backend

"""

import logging
from typing import Annotated

from aws_library.s3 import S3AccessError
from fastapi import APIRouter, Depends, Request
from models_library.api_schemas_storage.storage_schemas import HealthCheck, S3BucketName
from models_library.app_diagnostics import AppStatusCheck
from models_library.errors import REDIS_CLIENT_UNHEALTHY_MSG
from models_library.generics import Envelope
from pydantic import TypeAdapter
from servicelib.db_asyncpg_utils import check_postgres_liveness
from servicelib.fastapi.db_asyncpg_engine import get_engine
from servicelib.redis import RedisClientsManager
from simcore_postgres_database.utils_aiosqlalchemy import get_pg_engine_stateinfo

from ..._meta import API_VERSION, PROJECT_NAME, VERSION
from ...core.settings import get_application_settings
from ...modules.s3 import get_s3_client
from .dependencies.redis import get_redis_client_manager_from_request

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "status",
    ],
)


class HealthCheckError(RuntimeError):
    """Failed a health check"""


@router.get("/", include_in_schema=True, response_model=Envelope[HealthCheck])
async def get_health(
    request: Request,
    redis_client_manager: Annotated[RedisClientsManager, Depends(get_redis_client_manager_from_request)],
) -> Envelope[HealthCheck]:
    # NOTE: celery uses rabbitmq internally and retry options have already been setup
    if not redis_client_manager.healthy:
        raise HealthCheckError(REDIS_CLIENT_UNHEALTHY_MSG)

    assert request  # nosec
    return Envelope[HealthCheck](
        data=HealthCheck(
            name=PROJECT_NAME,
            version=f"{VERSION}",
            api_version=API_VERSION,
            status=None,
        )
    )


@router.get("/status", response_model=Envelope[AppStatusCheck])
async def get_status(request: Request) -> Envelope[AppStatusCheck]:
    # NOTE: all calls here must NOT raise
    assert request.app  # nosec
    app_settings = get_application_settings(request.app)
    s3_state = "disabled"
    if app_settings.STORAGE_S3:
        try:
            s3_state = (
                "connected"
                if await get_s3_client(request.app).bucket_exists(
                    bucket=TypeAdapter(S3BucketName).validate_python(app_settings.STORAGE_S3.S3_BUCKET_NAME)
                )
                else "no access to S3 bucket"
            )
        except S3AccessError:
            s3_state = "failed"

    postgres_state = "disabled"

    if app_settings.STORAGE_POSTGRES:
        postgres_state = "connected" if await check_postgres_liveness(get_engine(request.app)) else "failed"

    status = AppStatusCheck.model_validate(
        {
            "app_name": PROJECT_NAME,
            "version": f"{VERSION}",
            "services": {
                "postgres": {
                    "healthy": postgres_state,
                    "pool": await get_pg_engine_stateinfo(get_engine(request.app)),
                },
                "s3": {"healthy": s3_state},
            },
        }
    )
    return Envelope[AppStatusCheck](data=status)

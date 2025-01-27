"""

- Checks connectivity with other services in the backend

"""

import logging

from aws_library.s3 import S3AccessError
from fastapi import APIRouter, Request
from models_library.api_schemas_storage import HealthCheck, S3BucketName
from models_library.app_diagnostics import AppStatusCheck
from models_library.generics import Envelope
from pydantic import TypeAdapter
from servicelib.db_asyncpg_utils import check_postgres_liveness
from servicelib.fastapi.db_asyncpg_engine import get_engine
from simcore_postgres_database.utils_aiosqlalchemy import get_pg_engine_stateinfo

from ..._meta import API_VERSION, API_VTAG, PROJECT_NAME, VERSION
from ...core.settings import get_application_settings
from ...modules.s3 import get_s3_client

_logger = logging.getLogger(__name__)

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "status",
    ],
)


@router.get(
    f"/{API_VTAG}/", include_in_schema=True, response_model=Envelope[HealthCheck]
)
async def get_health(
    request: Request,
) -> Envelope[HealthCheck]:
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
    return Envelope[AppStatusCheck](data=status)

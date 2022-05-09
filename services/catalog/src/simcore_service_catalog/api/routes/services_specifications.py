import logging

from fastapi import APIRouter
from models_library.services import ServiceKey, ServiceVersion

from ...models.schemas.constants import RESPONSE_MODEL_POLICY

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/{service_key:path}/{service_version}/specifications",
    response_model=dict,
    **RESPONSE_MODEL_POLICY,
)
# @cached(
#     ttl=DIRECTOR_CACHING_TTL,
#     key_builder=lambda f, *args, **kwargs: f"{f.__name__}_{kwargs['service_key']}_{kwargs['service_version']}",
# )
async def get_service_specifications(
    service_key: ServiceKey,
    service_version: ServiceVersion,
):
    logger.debug("getting specifications for '%s:%s'", service_key, service_version)
    return {}

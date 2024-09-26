import arrow
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def check_service_health():
    # TODO: refactor to take into consideration RabbitMQ
    return f"{__name__}@{arrow.utcnow().datetime.isoformat()}"

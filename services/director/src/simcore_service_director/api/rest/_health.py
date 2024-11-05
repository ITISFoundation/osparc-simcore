import arrow
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.api_route(
    "/",
    methods=["GET", "HEAD"],
    include_in_schema=False,
    response_class=PlainTextResponse,
)
async def health_check() -> str:
    # NOTE: sync url in docker/healthcheck.py with this entrypoint!
    return f"{__name__}.health_check@{arrow.utcnow().isoformat()}"

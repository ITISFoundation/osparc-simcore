import arrow
from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

router = APIRouter()


@router.get("/", response_class=PlainTextResponse)
async def healthcheck():
    return f"{__name__}@{arrow.utcnow().isoformat()}"

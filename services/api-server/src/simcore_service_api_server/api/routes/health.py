from fastapi import APIRouter

router = APIRouter()


@router.get("/", include_in_schema=False)
async def check_service_health():
    return ":-)"

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def check_service_health():
    return {"msg": "I am healthy :-)"}

from typing import Dict

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
async def check_service_health() -> Dict[str, str]:
    return {"msg": "I am healthy :-)"}

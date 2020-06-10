from fastapi import APIRouter

# from .__version__ import __version__, api_version, api_vtag

router = APIRouter()


@router.get("", include_in_schema=False)
async def check_service_health():
    # TODO: if not, raise ServiceUnavailable (use diagnostic concept as in webserver)
    return

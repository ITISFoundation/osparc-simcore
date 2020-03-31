from fastapi import APIRouter

from .__version__ import __version__, api_version

router = APIRouter()


@router.get("/")
async def healthcheck():
    return {
        "name": __name__.split(".")[0],
        "version": __version__,
        "api_version": api_version,
    }

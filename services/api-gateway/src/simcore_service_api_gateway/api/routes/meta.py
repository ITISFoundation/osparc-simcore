from fastapi import APIRouter

from ...__version__ import __version__, api_version, api_vtag

router = APIRouter()


@router.get("")
async def get_service_metadata():
    return {
        "name": __name__.split(".")[0],
        "version": api_version,
        # TODO: a way to get first part of the url?? "version_prefix": f"/{api_vtag}",
        # TODO: sync this info
        "released": {api_vtag: api_version},
    }

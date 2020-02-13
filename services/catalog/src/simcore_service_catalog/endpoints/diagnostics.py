
from fastapi import APIRouter

from ..__version__ import __version__

router = APIRouter()



@router.get("/")
async def healthcheck():
    # TODO: this is the entrypoint that docker uses to determin whether the service is starting, failed, etc...
    # TODO: Reaching this point, what does it means? How is the health of this service? when shall it respond non-succesful?
    return {
        'name':__name__.split('.')[0],
        'version': __version__,
        'status': 'SERVICE_RUNNING',
        'api_version': __version__
    }

from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app
from simcore_service_api_server._service_programs import ProgramService


async def get_program_service(
    app: Annotated[FastAPI, Depends(get_app)],
) -> ProgramService:
    return ProgramService.get_from_app_state(app=app)

from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app
from simcore_service_api_server._service_job import JobService
from simcore_service_api_server.services_http.webserver import AuthSession

from .webserver_http import get_webserver_session


async def get_job_service(
    app: Annotated[FastAPI, Depends(get_app)],
    webserver_api: Annotated[AuthSession, Depends(get_webserver_session)],
) -> JobService:
    job_service = JobService.get_from_app_state(app=app)
    job_service._webserver_api = webserver_api
    return job_service

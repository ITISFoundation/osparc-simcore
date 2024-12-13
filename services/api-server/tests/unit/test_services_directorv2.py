# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
from fastapi import FastAPI, status
from httpx import AsyncClient
from models_library.projects import ProjectID
from models_library.users import UserID
from respx import MockRouter
from settings_library.director_v2 import DirectorV2Settings
from simcore_service_api_server.exceptions.backend_errors import JobNotFoundError
from simcore_service_api_server.services_http.director_v2 import DirectorV2Api


@pytest.fixture
def api() -> DirectorV2Api:
    settings = DirectorV2Settings()
    app = FastAPI()

    return DirectorV2Api.create_once(
        app=app,
        client=AsyncClient(base_url=settings.base_url),
        service_name="director_v2",
    )


async def test_oec_139646582688800_missing_ctx_values_for_msg_template(
    mocked_directorv2_service_api_base: MockRouter,
    project_id: ProjectID,
    user_id: UserID,
    api: DirectorV2Api,
):
    #
    # tests to reproduce reported OEC:139646582688800
    #

    #   File "/home/scu/.venv/lib/python3.10/site-packages/simcore_service_api_server/services/director_v2.py", line 135, in get_computation
    #     response.raise_for_status()
    #   File "/home/scu/.venv/lib/python3.10/site-packages/httpx/_models.py", line 761, in raise_for_status
    #     raise HTTPStatusError(message, request=request, response=self)
    # httpx.HTTPStatusError: Client error '404 Not Found' for url '/v2/computations/c7ad07d3-513f-4368-bcf0-354143b6a048?user_id=94'

    for method in ("GET", "POST", "DELETE"):
        mocked_directorv2_service_api_base.request(
            method,
            path__regex=r"/v2/computations/",
        ).respond(status_code=status.HTTP_404_NOT_FOUND)

    #  File "/home/scu/.venv/lib/python3.10/site-packages/simcore_service_api_server/exceptions/service_errors_utils.py", line 116, in service_exception_handler
    #    status_code, detail, headers = _get_http_exception_kwargs(
    #  File "/home/scu/.venv/lib/python3.10/site-packages/simcore_service_api_server/exceptions/service_errors_utils.py", line 66, in _get_http_exception_kwargs
    #    raise exception_type(**detail_kwargs)
    # simcore_service_api_server.exceptions.backend_errors.JobNotFoundError: <exception str() failed>  <-- !!!!!!!!!
    #
    # File "/home/scu/.venv/lib/python3.10/site-packages/simcore_service_api_server/exceptions/handlers/_handlers_backend_errors.py", line 12, in backend_error_handler
    #     return create_error_json_response(f"{exc}", status_code=exc.status_code)
    #   File "pydantic/errors.py", line 127, in pydantic.errors.PydanticErrorMixin.__str__
    # KeyError: 'project_id'
    #

    with pytest.raises(JobNotFoundError, match=f"{project_id}"):
        await api.get_computation(user_id=user_id, project_id=project_id)

    with pytest.raises(JobNotFoundError, match=f"{project_id}"):
        await api.stop_computation(user_id=user_id, project_id=project_id)

    with pytest.raises(JobNotFoundError, match=f"{project_id}"):
        await api.delete_computation(user_id=user_id, project_id=project_id)

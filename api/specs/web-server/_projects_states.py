# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Body, Depends
from models_library.api_schemas_webserver.projects import ProjectGet
from models_library.generics import Envelope
from models_library.projects_state import ProjectState
from pydantic import ValidationError
from servicelib.aiohttp import status
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.director_v2.exceptions import DirectorV2ServiceError
from simcore_service_webserver.projects._controller.projects_states_rest import (
    ProjectPathParams,
    _OpenProjectQuery,
)
from simcore_service_webserver.projects.exceptions import (
    ProjectInvalidRightsError,
    ProjectNotFoundError,
    ProjectTooManyProjectOpenedError,
)
from simcore_service_webserver.users.exceptions import UserDefaultWalletNotFoundError
from simcore_service_webserver.wallets.errors import WalletNotEnoughCreditsError

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "projects",
    ],
)


def to_desc(exceptions: list[type[Exception]] | type[Exception]):
    exc_classes = [exceptions] if not isinstance(exceptions, list) else exceptions
    return ", ".join(f"{cls.__name__}" for cls in exc_classes)


@router.post(
    "/projects/{project_id}:open",
    response_model=Envelope[ProjectGet],
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": to_desc([ValidationError])},
        status.HTTP_402_PAYMENT_REQUIRED: {
            "description": to_desc([WalletNotEnoughCreditsError])
        },
        status.HTTP_403_FORBIDDEN: {
            "description": to_desc([ProjectInvalidRightsError])
        },
        status.HTTP_404_NOT_FOUND: {
            "description": to_desc(
                [ProjectNotFoundError, UserDefaultWalletNotFoundError]
            )
        },
        status.HTTP_409_CONFLICT: {
            "description": to_desc([ProjectTooManyProjectOpenedError]),
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": to_desc([ValidationError])
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": to_desc([DirectorV2ServiceError])
        },
    },
)
def open_project(
    client_session_id: Annotated[str, Body(...)],
    _path_params: Annotated[ProjectPathParams, Depends()],
    _query_params: Annotated[_OpenProjectQuery, Depends()],
): ...


@router.post("/projects/{project_id}:close", status_code=status.HTTP_204_NO_CONTENT)
def close_project(
    _path_params: Annotated[ProjectPathParams, Depends()],
    client_session_id: Annotated[str, Body(...)],
): ...


@router.get("/projects/{project_id}/state", response_model=Envelope[ProjectState])
def get_project_state(
    _path_params: Annotated[ProjectPathParams, Depends()],
): ...

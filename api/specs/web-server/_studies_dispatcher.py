# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.generics import Envelope
from pydantic import BaseModel
from simcore_service_webserver._meta import API_VTAG

router = APIRouter(
    prefix=f"/{API_VTAG}",
    tags=[
        "studies-dispatcher",
    ],
)


class _DispatchQueryParams(BaseModel):
    """Query parameters for the dispatch endpoint (template parameters)."""

    # Empty base, query params are passed as-is from template_parameters


@router.post(
    "/studies/{study_id}:dispatch",
    response_model=Envelope[TaskGet],
    description="Start an async clone of a published study into the requesting user's account",
    status_code=status.HTTP_202_ACCEPTED,
    name="dispatch_study",
)
async def dispatch_study(
    study_id: str,
    _query: Annotated[as_query(_DispatchQueryParams), Depends()] = None,
): ...

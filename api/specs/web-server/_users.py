# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from _common import Error, Log
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.users_preferences import PatchRequestBody
from models_library.generics import Envelope
from models_library.user_preferences import PreferenceIdentifier
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.users._handlers import (
    _NotificationPathParams,
    _TokenPathParams,
)
from simcore_service_webserver.users._notifications import (
    UserNotification,
    UserNotificationCreate,
    UserNotificationPatch,
)
from simcore_service_webserver.users.schemas import (
    PermissionGet,
    ProfileDeleteCheck,
    ProfileGet,
    ProfileUpdate,
    Token,
    TokenCreate,
)

router = APIRouter(prefix=f"/{API_VTAG}", tags=["user"])


@router.get(
    "/me",
    response_model=Envelope[ProfileGet],
)
async def get_my_profile():
    ...


@router.put(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_my_profile(_profile: ProfileUpdate):
    ...


@router.post(
    "/me:mark-deleted",
    response_model=Envelope[Log],
    status_code=status.HTTP_200_OK,
    responses={status.HTTP_409_CONFLICT: {"model": Envelope[Error]}},
)
async def mark_account_for_deletion(_body: ProfileDeleteCheck):
    ...


@router.patch(
    "/me/preferences/{preference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_frontend_preference(
    preference_id: PreferenceIdentifier,  # noqa: ARG001
    body_item: PatchRequestBody,  # noqa: ARG001
):
    ...


@router.get(
    "/me/tokens",
    response_model=Envelope[list[Token]],
)
async def list_tokens():
    ...


@router.post(
    "/me/tokens",
    response_model=Envelope[Token],
    status_code=status.HTTP_201_CREATED,
)
async def create_token(_token: TokenCreate):
    ...


@router.get(
    "/me/tokens/{service}",
    response_model=Envelope[Token],
)
async def get_token(_params: Annotated[_TokenPathParams, Depends()]):
    ...


@router.delete(
    "/me/tokens/{service}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_token(_params: Annotated[_TokenPathParams, Depends()]):
    ...


@router.get(
    "/me/notifications",
    response_model=Envelope[list[UserNotification]],
)
async def list_user_notifications():
    ...


@router.post(
    "/me/notifications",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def create_user_notification(_notification: UserNotificationCreate):
    ...


@router.patch(
    "/me/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mark_notification_as_read(
    _params: Annotated[_NotificationPathParams, Depends()],
    _notification: UserNotificationPatch,
):
    ...


@router.get(
    "/me/permissions",
    response_model=Envelope[list[PermissionGet]],
)
async def list_user_permissions():
    ...

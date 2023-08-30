# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.users_preferences import (
    FrontendUserPreferencePatchPathParams,
    FrontendUserPreferencePatchRequestBody,
    FrontendUserPreferencesGet,
)
from models_library.generics import Envelope
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


@router.get(
    "/me/preferences",
    response_model=Envelope[FrontendUserPreferencesGet],
)
async def get_user_preferences():
    ...


@router.patch(
    "/me/preferences/{frontend_preference_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_frontend_preference(
    _params: Annotated[FrontendUserPreferencePatchPathParams, Depends()],
    _preference: FrontendUserPreferencePatchRequestBody,
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

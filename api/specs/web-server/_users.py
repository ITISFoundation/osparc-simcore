# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.users import (
    MyPermissionGet,
    MyProfileGet,
    MyProfilePatch,
    MyTokenCreate,
    MyTokenGet,
    MyUserGet,
    MyUsersSearchQueryParams,
    UserGet,
    UsersSearchQueryParams,
)
from models_library.api_schemas_webserver.users_preferences import PatchRequestBody
from models_library.generics import Envelope
from models_library.user_preferences import PreferenceIdentifier
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.users._common.schemas import PreRegisteredUserGet
from simcore_service_webserver.users._notifications import (
    UserNotification,
    UserNotificationCreate,
    UserNotificationPatch,
)
from simcore_service_webserver.users._notifications_rest import _NotificationPathParams
from simcore_service_webserver.users._tokens_rest import _TokenPathParams

router = APIRouter(prefix=f"/{API_VTAG}", tags=["user"])


@router.get(
    "/me",
    response_model=Envelope[MyProfileGet],
)
async def get_my_profile():
    ...


@router.patch(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_my_profile(_profile: MyProfilePatch):
    ...


@router.put(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    deprecated=True,
    description="Use PATCH instead",
)
async def replace_my_profile(_profile: MyProfilePatch):
    ...


@router.patch(
    "/me/preferences/{preference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_frontend_preference(
    preference_id: PreferenceIdentifier,
    body_item: PatchRequestBody,
):
    ...


@router.get(
    "/me/tokens",
    response_model=Envelope[list[MyTokenGet]],
)
async def list_tokens():
    ...


@router.post(
    "/me/tokens",
    response_model=Envelope[MyTokenGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_token(_token: MyTokenCreate):
    ...


@router.get(
    "/me/tokens/{service}",
    response_model=Envelope[MyTokenGet],
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
    response_model=Envelope[list[MyPermissionGet]],
)
async def list_user_permissions():
    ...


@router.get(
    "/me/users:search",
    response_model=Envelope[list[MyUserGet]],
    description="Search among users who are publicly visible to the caller (i.e., me) based on their privacy settings.",
)
async def search_users(_params: Annotated[MyUsersSearchQueryParams, Depends()]):
    ...


_extra_tags: list[str | Enum] = ["admin"]


@router.get(
    "/users:search",
    response_model=Envelope[list[UserGet]],
    tags=_extra_tags,
)
async def search_users_as_admin(_params: Annotated[UsersSearchQueryParams, Depends()]):
    # NOTE: see `Search` in `Common Custom Methods` in https://cloud.google.com/apis/design/custom_methods
    ...


@router.post(
    "/users:pre-register",
    response_model=Envelope[UserGet],
    tags=_extra_tags,
)
async def pre_register_user_as_admin(_body: PreRegisteredUserGet):
    ...

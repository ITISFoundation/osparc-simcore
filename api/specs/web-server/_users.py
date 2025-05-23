# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated

from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.users import (
    MyPermissionGet,
    MyProfileGet,
    MyProfilePatch,
    MyTokenCreate,
    MyTokenGet,
    UserAccountApprove,
    UserAccountGet,
    UserAccountReject,
    UserAccountSearchQueryParams,
    UserGet,
    UsersAccountListQueryParams,
    UsersSearch,
)
from models_library.api_schemas_webserver.users_preferences import PatchRequestBody
from models_library.generics import Envelope
from models_library.rest_pagination import Page
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

router = APIRouter(prefix=f"/{API_VTAG}", tags=["users"])


@router.get(
    "/me",
    response_model=Envelope[MyProfileGet],
)
async def get_my_profile(): ...


@router.patch(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_my_profile(_body: MyProfilePatch): ...


@router.patch(
    "/me/preferences/{preference_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def set_frontend_preference(
    preference_id: PreferenceIdentifier,
    _body: PatchRequestBody,
): ...


@router.get(
    "/me/tokens",
    response_model=Envelope[list[MyTokenGet]],
)
async def list_tokens(): ...


@router.post(
    "/me/tokens",
    response_model=Envelope[MyTokenGet],
    status_code=status.HTTP_201_CREATED,
)
async def create_token(_body: MyTokenCreate): ...


@router.get(
    "/me/tokens/{service}",
    response_model=Envelope[MyTokenGet],
)
async def get_token(
    _path: Annotated[_TokenPathParams, Depends()],
): ...


@router.delete(
    "/me/tokens/{service}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_token(_path: Annotated[_TokenPathParams, Depends()]): ...


@router.get(
    "/me/notifications",
    response_model=Envelope[list[UserNotification]],
)
async def list_user_notifications(): ...


@router.post(
    "/me/notifications",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def create_user_notification(
    _body: UserNotificationCreate,
): ...


@router.patch(
    "/me/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def mark_notification_as_read(
    _path: Annotated[_NotificationPathParams, Depends()],
    _body: UserNotificationPatch,
): ...


@router.get(
    "/me/permissions",
    response_model=Envelope[list[MyPermissionGet]],
)
async def list_user_permissions(): ...


#
# USERS public
#


@router.post(
    "/users:search",
    response_model=Envelope[list[UserGet]],
    description="Search among users who are publicly visible to the caller (i.e., me) based on their privacy settings.",
)
async def search_users(_body: UsersSearch): ...


#
# USERS admin
#

_extra_tags: list[str | Enum] = ["admin"]


@router.get(
    "/admin/user-accounts",
    response_model=Page[UserAccountGet],
    tags=_extra_tags,
)
async def list_users_accounts(
    _query: Annotated[as_query(UsersAccountListQueryParams), Depends()],
): ...


@router.post(
    "/admin/user-accounts:approve",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=_extra_tags,
)
async def approve_user_account(_body: UserAccountApprove): ...


@router.post(
    "/admin/user-accounts:reject",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=_extra_tags,
)
async def reject_user_account(_body: UserAccountReject): ...


@router.get(
    "/admin/user-accounts:search",
    response_model=Envelope[list[UserAccountGet]],
    tags=_extra_tags,
)
async def search_user_accounts(
    _query: Annotated[UserAccountSearchQueryParams, Depends()],
):
    # NOTE: see `Search` in `Common Custom Methods` in https://cloud.google.com/apis/design/custom_methods
    ...


@router.post(
    "/admin/user-accounts:pre-register",
    response_model=Envelope[UserAccountGet],
    tags=_extra_tags,
)
async def pre_register_user_account(_body: PreRegisteredUserGet): ...

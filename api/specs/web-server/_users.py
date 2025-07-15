# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Annotated

from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.users import (
    MyFunctionPermissionsGet,
    MyPermissionGet,
    MyPhoneConfirm,
    MyPhoneRegister,
    MyProfileRestGet,
    MyProfileRestPatch,
    MyTokenCreate,
    MyTokenGet,
    TokenPathParams,
    UserGet,
    UsersSearch,
)
from models_library.api_schemas_webserver.users_preferences import PatchRequestBody
from models_library.generics import Envelope
from models_library.user_preferences import PreferenceIdentifier
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.user_notifications._controller.rest.user_notification_rest import (
    NotificationPathParams,
)
from simcore_service_webserver.user_notifications._models import (
    UserNotification,
    UserNotificationCreate,
    UserNotificationPatch,
)

router = APIRouter(prefix=f"/{API_VTAG}", tags=["users"])


@router.get(
    "/me",
    response_model=Envelope[MyProfileRestGet],
)
async def get_my_profile(): ...


@router.patch(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_my_profile(_body: MyProfileRestPatch): ...


@router.post(
    "/me/phone:register",
    description="Starts the phone registration process",
    status_code=status.HTTP_202_ACCEPTED,
)
async def my_phone_register(_body: MyPhoneRegister): ...


@router.post(
    "/me/phone:resend",
    description="Resends the phone registration code",
    status_code=status.HTTP_202_ACCEPTED,
)
async def my_phone_resend(): ...


@router.post(
    "/me/phone:confirm",
    description="Confirms the phone registration",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def my_phone_confirm(_body: MyPhoneConfirm): ...


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
    _path: Annotated[TokenPathParams, Depends()],
): ...


@router.delete(
    "/me/tokens/{service}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_token(_path: Annotated[TokenPathParams, Depends()]): ...


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
    _path: Annotated[NotificationPathParams, Depends()],
    _body: UserNotificationPatch,
): ...


@router.get(
    "/me/permissions",
    response_model=Envelope[list[MyPermissionGet]],
)
async def list_user_permissions(): ...


@router.get(
    "/me/function-permissions",
    response_model=Envelope[MyFunctionPermissionsGet],
)
async def list_user_functions_permissions(): ...


#
# USERS public
#


@router.post(
    "/users:search",
    response_model=Envelope[list[UserGet]],
    description="Search among users who are publicly visible to the caller (i.e., me) based on their privacy settings.",
)
async def search_users(_body: UsersSearch): ...

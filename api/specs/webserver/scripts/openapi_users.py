""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated

from fastapi import Depends, FastAPI, status
from models_library.generics import Envelope
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

# from simcore_service_webserver.users._handlers import

app = FastAPI(redoc_url=None)

TAGS: list[str | Enum] = [
    "user",
]


@app.get(
    "/me",
    response_model=Envelope[ProfileGet],
    tags=TAGS,
    operation_id="get_my_profile",
)
async def get_user_profile():
    ...


@app.put(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS,
    operation_id="update_my_profile",
)
async def update_my_profile(profile: ProfileUpdate):
    ...


@app.get(
    "/me/tokens",
    response_model=Envelope[list[Token]],
    tags=TAGS,
    operation_id="list_tokens",
)
async def list_tokens():
    ...


@app.post(
    "/me/tokens",
    response_model=Envelope[Token],
    status_code=status.HTTP_201_CREATED,
    tags=TAGS,
    operation_id="create_token",
)
async def create_token(token: TokenCreate):
    ...


@app.get(
    "/me/tokens/{service}",
    response_model=Envelope[Token],
    tags=TAGS,
    operation_id="get_token",
)
async def get_token(params: Annotated[_TokenPathParams, Depends()]):
    ...


@app.delete(
    "/me/tokens/{service}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS,
    operation_id="delete_token",
)
async def delete_token(params: Annotated[_TokenPathParams, Depends()]):
    ...


@app.get(
    "/me/notifications",
    response_model=Envelope[list[UserNotification]],
    tags=TAGS,
    operation_id="list_user_notifications",
)
async def list_user_notifications():
    ...


@app.post(
    "/me/notifications",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS,
    operation_id="create_user_notification",
)
async def create_user_notification(notification: UserNotificationCreate):
    ...


@app.patch(
    "/me/notifications/{notification_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS,
    operation_id="mark_notification_as_read",
)
async def mark_notification_as_read(
    params: Annotated[_NotificationPathParams, Depends()],
    notification: UserNotificationPatch,
):
    ...


@app.get(
    "/me/permissions",
    response_model=Envelope[list[PermissionGet]],
    tags=TAGS,
    operation_id="list_user_permissions",
)
async def list_user_permissions():
    ...


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi-users.yaml")

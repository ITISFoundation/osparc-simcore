# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from enum import Enum
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from models_library.api_schemas_webserver.users import (
    PageQueryParameters,
    UserAccountApprove,
    UserAccountGet,
    UserAccountReject,
    UserAccountSearchQueryParams,
    UsersForAdminListFilter,
)
from models_library.generics import Envelope
from models_library.rest_pagination import Page
from simcore_service_webserver._meta import API_VTAG
from simcore_service_webserver.users.schemas import UserAccountRestPreRegister

router = APIRouter(prefix=f"/{API_VTAG}", tags=["users"])

_extra_tags: list[str | Enum] = ["admin"]


# NOTE: I still do not have a clean solution for this
#
class _Q(UsersForAdminListFilter, PageQueryParameters): ...


@router.get(
    "/admin/user-accounts",
    response_model=Page[UserAccountGet],
    tags=_extra_tags,
)
async def list_users_accounts(
    _query: Annotated[_Q, Depends()],
    order_by: Annotated[
        str,
        Query(
            title="Order By",
            description="Comma-separated list of fields for ordering (prefix with '-' for descending).",
            example="-created_at,name",
        ),
    ] = "",
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
async def pre_register_user_account(_body: UserAccountRestPreRegister): ...

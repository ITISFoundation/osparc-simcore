import logging
from contextlib import suppress

from aiohttp import web
from models_library.api_schemas_webserver.users import (
    MyProfileRestGet,
    MyProfileRestPatch,
    UserGet,
    UsersSearch,
)
from servicelib.aiohttp import status
from servicelib.aiohttp.requests_validation import (
    parse_request_body_as,
)
from simcore_service_webserver.application_settings_utils import (
    requires_dev_feature_enabled,
)

from ...._meta import API_VTAG
from ....groups import api as groups_service
from ....groups.exceptions import GroupNotFoundError
from ....login.decorators import login_required
from ....products import products_web
from ....products.models import Product
from ....security.decorators import permission_required
from ....session.api import get_session
from ....utils_aiohttp import envelope_json_response
from ... import _users_service
from ..._users_web import RegistrationSessionManager
from ._rest_exceptions import handle_rest_requests_exceptions
from ._rest_schemas import MyPhoneConfirm, MyPhoneRegister, UsersRequestContext

_logger = logging.getLogger(__name__)

_REGISTRATION_CODE_VALUE_FAKE = (
    "123456"  # NOTE: temporary fake while developing registration feature
)


routes = web.RouteTableDef()

#
# MY PROFILE: /me
#


@routes.get(f"/{API_VTAG}/me", name="get_my_profile")
@login_required
@handle_rest_requests_exceptions
async def get_my_profile(request: web.Request) -> web.Response:
    product: Product = products_web.get_current_product(request)
    req_ctx = UsersRequestContext.model_validate(request)

    groups_by_type = await groups_service.list_user_groups_with_read_access(
        request.app, user_id=req_ctx.user_id
    )

    assert groups_by_type.primary
    assert groups_by_type.everyone

    my_product_group = None

    if product.group_id:
        with suppress(GroupNotFoundError):
            # Product is optional
            my_product_group = await groups_service.get_product_group_for_user(
                app=request.app,
                user_id=req_ctx.user_id,
                product_gid=product.group_id,
            )

    my_profile, preferences = await _users_service.get_my_profile(
        request.app, user_id=req_ctx.user_id, product_name=req_ctx.product_name
    )

    profile = MyProfileRestGet.from_domain_model(
        my_profile, groups_by_type, my_product_group, preferences
    )

    return envelope_json_response(profile)


@routes.patch(f"/{API_VTAG}/me", name="update_my_profile")
@login_required
@permission_required("user.profile.update")
@handle_rest_requests_exceptions
async def update_my_profile(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    profile_update = await parse_request_body_as(MyProfileRestPatch, request)

    await _users_service.update_my_profile(
        request.app, user_id=req_ctx.user_id, update=profile_update
    )
    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# PHONE REGISTRATION: /me/phone:*
#


@routes.post(f"/{API_VTAG}/me/phone:register", name="my_phone_register")
@login_required
@permission_required("user.profile.update")
@requires_dev_feature_enabled
@handle_rest_requests_exceptions
async def my_phone_register(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    phone_register = await parse_request_body_as(MyPhoneRegister, request)

    session = await get_session(request)
    registration_session_manager = RegistrationSessionManager(
        session, req_ctx.user_id, req_ctx.product_name
    )
    registration_session_manager.start_registration(
        phone_register.phone, code=_REGISTRATION_CODE_VALUE_FAKE
    )

    return web.json_response(status=status.HTTP_202_ACCEPTED)


@routes.post(f"/{API_VTAG}/me/phone:resend", name="my_phone_resend")
@login_required
@permission_required("user.profile.update")
@requires_dev_feature_enabled
@handle_rest_requests_exceptions
async def my_phone_resend(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)

    session = await get_session(request)
    registration_session_manager = RegistrationSessionManager(
        session, req_ctx.user_id, req_ctx.product_name
    )
    registration_session_manager.regenerate_code(new_code=_REGISTRATION_CODE_VALUE_FAKE)

    return web.json_response(status=status.HTTP_202_ACCEPTED)


@routes.post(f"/{API_VTAG}/me/phone:confirm", name="my_phone_confirm")
@login_required
@permission_required("user.profile.update")
@requires_dev_feature_enabled
@handle_rest_requests_exceptions
async def my_phone_confirm(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    phone_confirm = await parse_request_body_as(MyPhoneConfirm, request)

    session = await get_session(request)
    registration_session_manager = RegistrationSessionManager(
        session, req_ctx.user_id, req_ctx.product_name
    )

    registration = registration_session_manager.validate_pending_registration()
    registration_session_manager.validate_confirmation_code(phone_confirm.code)

    await _users_service.update_user_phone(
        request.app,
        user_id=req_ctx.user_id,
        phone=registration["data"],
    )

    registration_session_manager.clear_session()

    return web.json_response(status=status.HTTP_204_NO_CONTENT)


#
# USERS (public)
#


@routes.post(f"/{API_VTAG}/users:search", name="search_users")
@login_required
@permission_required("user.read")
@handle_rest_requests_exceptions
async def search_users(request: web.Request) -> web.Response:
    req_ctx = UsersRequestContext.model_validate(request)
    assert req_ctx.product_name  # nosec

    # NOTE: Decided for body instead of query parameters because it is easier for the front-end
    search_params = await parse_request_body_as(UsersSearch, request)

    found = await _users_service.search_public_users(
        request.app,
        caller_id=req_ctx.user_id,
        match_=search_params.match_,
        limit=search_params.limit,
    )

    return envelope_json_response([UserGet.from_domain_model(user) for user in found])

""" Creates all routes for authentication/authorization subsystem by
    mapping all routes defined under /auth/ path and subsystem's handlers

"""

import logging
from pprint import pformat

from aiohttp import web
from servicelib.aiohttp import openapi
from servicelib.aiohttp.rest_routing import (
    iter_path_operations,
    map_handlers_with_operations,
)

from . import api_keys_handlers, handlers_2fa
from . import handlers_auth as login_handlers
from . import handlers_change as change_handlers
from . import handlers_confirmation as confirmation_handlers
from . import handlers_registration as register_handlers

log = logging.getLogger(__name__)


def create_routes(validated_specs: openapi.Spec) -> list[web.RouteDef]:
    """Creates routes mapping operators_id with handler functions"""

    base_path = openapi.get_base_path(validated_specs)

    def include_path(tuple_object):
        _method, path, _operation_id, _tags = tuple_object
        return path.startswith(base_path + "/auth/")

    handlers_map = {
        "auth_change_email": change_handlers.submit_request_to_change_email,
        "auth_change_password": change_handlers.change_password,
        "auth_check_registration_invitation": register_handlers.check_registration_invitation,
        "auth_confirmation": confirmation_handlers.validate_confirmation_and_redirect,
        "auth_login_2fa": login_handlers.login_2fa,
        "auth_login": login_handlers.login,
        "auth_logout": login_handlers.logout,
        "auth_phone_confirmation": confirmation_handlers.phone_confirmation,
        "auth_register_phone": register_handlers.register_phone,
        "auth_register": register_handlers.register,
        "auth_resend_2fa_code": handlers_2fa.resend_2fa_code,
        "auth_reset_password_allowed": confirmation_handlers.reset_password,
        "auth_reset_password": change_handlers.submit_request_to_reset_password,
        "create_api_key": api_keys_handlers.create_api_key,
        "delete_api_key": api_keys_handlers.delete_api_key,
        "list_api_keys": api_keys_handlers.list_api_keys,
    }

    routes: list[web.RouteDef] = map_handlers_with_operations(
        handlers_map,
        filter(include_path, iter_path_operations(validated_specs)),
        strict=True,
    )

    log.debug("Mapped auth routes: %s", "\n".join([pformat(r) for r in routes]))

    return routes

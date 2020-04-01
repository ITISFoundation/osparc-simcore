""" Basic diagnostic handles to the rest API for operations


"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import wrap_as_envelope
from servicelib.rest_utils import body_to_dict, extract_and_validate

from . import __version__
from .diagnostics_handlers import get_diagnostics, check_health

log = logging.getLogger(__name__)

# TODO: keep here until routes moved to diagnostics
__all__ = ["get_diagnostics", "check_health", "check_action", "get_config"]


async def check_action(request: web.Request):
    params, query, body = await extract_and_validate(request)

    assert params, "params %s" % params  # nosec
    assert query, "query %s" % query  # nosec
    assert body, "body %s" % body  # nosec

    if params["action"] == "fail":
        raise ValueError("some randome failure")

    # echo's input
    data = {
        "path_value": params["action"],
        "query_value": query["data"],
        "body_value": body_to_dict(body),
    }

    return wrap_as_envelope(data=data)


async def get_config(request: web.Request):
    """
        This entrypoint aims to provide an extra configuration mechanism for
        the front-end app.

        Some of the server configuration can be forwarded to the front-end here

        Example use case: the front-end app is served to the client. Then the user wants to
        register but the server has been setup to require an invitation. This option is setup
        at runtime and the front-end can only get it upon request to /config
    """
    await extract_and_validate(request)

    cfg = request.app[APP_CONFIG_KEY]
    login_cfg = cfg.get("login", {})

    # Schema api/specs/webserver/v0/components/schemas/config.yaml
    data = {
        "invitation_required": login_cfg.get("registration_invitation_required", False)
    }

    return data

""" Basic diagnostic handles to the rest API for operations


"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.rest_responses import wrap_as_envelope
from servicelib.rest_utils import body_to_dict, extract_and_validate

from . import __version__

log = logging.getLogger(__name__)


async def check_running(_request: web.Request):
    #
    # - This entry point is used as a fast way
    #   to check that the service is still running
    # - Do not do add any expensive computatio here
    # - Healthcheck has been moved to diagnostics module
    #
    data = {
        "name": __name__.split(".")[0],
        "version": str(__version__),
        "status": "SERVICE_RUNNING",
        "api_version": str(__version__),
    }
    return data


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

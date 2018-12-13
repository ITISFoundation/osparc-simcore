""" Implements handlers for
    api/specs/webserver/v0/openapi-node-v0.0.1.yaml


TODO: handlers implementation. Connect first to fake data for testing

:raises NotImplementedError
"""
from aiohttp import web
import logging
from ..login.decorators import login_required


log = logging.getLogger(__name__)

@login_required
async def get_node_output_ui(request: web.Request):
    """ Returns a json description of the ui for presenting the output within the mainUi
        and a list of open api json schema objects describing the possible
        json payloads and responses for the api calls available at this endpoint

    """
    log.debug(request.match_info["nodeInstanceUUID"],
              request.match_info["outputKey"]
    )

    raise NotImplementedError()


@login_required
async def send_to_node_output_api(request: web.Request):
    """ send data back to the output api ...
        protocol depends on the definition
    """
    body = await request.body
    log.debug(request.match_info["nodeInstanceUUID"],
              request.match_info["outputKey"],
              request.match_info["apiCall"],
              body
    )

    raise NotImplementedError()

@login_required
async def get_node_output_iframe(request: web.Request):
    """ entry point for iframe interaction with the node.
        This relies on the reverse proxy code.
    """
    log.debug(request.match_info["nodeInstanceUUID"])

    raise NotImplementedError()

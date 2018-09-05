"""This is a generated stub of handlers to be connected to the paths defined in the API

"""
# TODO: exceptions while developing ...
# pylint: disable=unused-argument
# pylint: disable=unused-import

import logging
import pkg_resources

from aiohttp import (
    web
)
from aiohttp_security import (
    remember, forget,
    has_permission, login_required
)

from ..settings import api_version

from .._generated_code.models.health_check import HealthCheck
from .._generated_code.models.health_check_enveloped import HealthCheckEnveloped


_LOGGER = logging.getLogger(__name__)


async def check_health(request):
    distb = pkg_resources.get_distribution('simcore-service-webserver')
    # TODO: add state of services (e.g. database not connected/failed, etc)

    # TODO: unify location of service info. setup.py should take if from there?
    info = HealthCheck(
        name = distb.project_name,
        status = "running",
        version = distb.version,
        api_version = api_version())

    return HealthCheckEnveloped(data=info, status=200)

@login_required
async def get_me(request):
    pass

@has_permission("tester")
async def ping(request):
    """
      ---
      description: This end-point allow to test that service is up.
      tags:
      - test
      produces:
      - text/plain
      responses:
          "200":
              description: successful operation. Return "pong" text
          "405":
              description: invalid HTTP Method
          "401":
              Unauthorized: need to login first
          "403":
              Forbidden: permission denied given the user"s privilege
    """
    _LOGGER.debug("ping with request %s", request)
    return web.Response(text="pong")

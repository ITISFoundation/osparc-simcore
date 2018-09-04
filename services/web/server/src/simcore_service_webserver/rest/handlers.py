"""This is a generated stub of handlers to be connected to the paths defined in the API

"""
import logging

import pkg_resources
from aiohttp import web_exceptions

from .generated_code.models.health_check import HealthCheck
from .generated_code.models.health_check_enveloped import HealthCheckEnveloped
from .generated_code.models.registration_input import RegistrationInput


_LOGGER = logging.getLogger(__name__)

async def check_health(request):
    distb = pkg_resources.get_distribution('simcore-service-webserver')

    # TODO: unify location of service info. setup.py should take if from there?
    info = HealthCheck(
        name = distb.project_name,
        status = "running",
        version = distb.version,
        api_version = "1.0")

    return HealthCheckEnveloped(data=info, status=200)

async def get_me(request):
    pass

#  TODO:  middleware to convert input-body from dict to RegistrationInput
async def register_user(request, input_body:RegistrationInput):
    pass

async def confirm_token(request):
    pass

async def login(request):
    pass

async def logout(request):
    pass

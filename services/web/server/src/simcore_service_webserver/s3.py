""" s3 subsystem

    Provides a client-sdk to interact with minio services
"""
import logging

from aiohttp import web

from servicelib.application_keys import APP_CONFIG_KEY
#TODO: from servicelib.application_setup import ModuleCategory, app_module_setup

from .s3_config import CONFIG_SECTION_NAME

#from s3wrapper.s3_client import S3Client

logger = logging.getLogger(__name__)

#TODO: @app_module_setup(__name__, ModuleCategory.ADDON, logger=logger)
def setup(app: web.Application):
    assert CONFIG_SECTION_NAME not in app[APP_CONFIG_KEY], "Temporarily disabled"

    # TODO: implement!!!

    # TODO: enable when sockets are refactored
    #cfg = app[APP_CONFIG_KEY][CONFIG_SECTION_NAME]
    #
    # client = S3Client(
    #         endpoint=cfg['endpoint'],
    #         access_key=cfg['access_key'],
    #         secret_key=cfg['secret_key'])

    # app["s3.client"] = client


# alias
setup_s3 = setup

__all__ = (
    'setup_s3'
)

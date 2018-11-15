""" Module to access s3 service

"""
import logging
from typing import Dict

from aiohttp import web

from .settings import APP_CONFIG_KEY

#from s3wrapper.s3_client import S3Client


log = logging.getLogger(__name__)

_SERVICE_NAME = 's3'


SIMCORE_S3_ID    = 0
SIMCORE_S3_STR   = "simcore.s3"

DATCORE_ID      = 1
DATCORE_STR     = "datcore"

def setup(app: web.Application):
    """ minio/s3 service setup"""

    log.debug("Setting up %s ...", __name__)
    disable_services = app[APP_CONFIG_KEY].get("main", {}).get("disable_services",[])

    if _SERVICE_NAME in disable_services:
        log.warning("Service '%s' explicitly disabled in config", _SERVICE_NAME)
        return

def get_config(app: web.Application) -> Dict:
    cfg = app[APP_CONFIG_KEY][_SERVICE_NAME]
    return cfg


# alias
setup_s3 = setup
get_config_s3 = get_config


__all__ = (
    "setup_s3",
    "get_config_s3",

)

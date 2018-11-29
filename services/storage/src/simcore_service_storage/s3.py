""" Module to access s3 service

"""
import logging
from typing import Dict

from aiohttp import web

from s3wrapper.s3_client import S3Client

from .settings import APP_CONFIG_KEY, APP_S3_KEY

log = logging.getLogger(__name__)

_SERVICE_NAME = 's3'

def setup(app: web.Application):
    """ minio/s3 service setup"""

    log.debug("Setting up %s ...", __name__)
    disable_services = app[APP_CONFIG_KEY].get("main", {}).get("disable_services",[])

    if _SERVICE_NAME in disable_services:
        log.warning("Service '%s' explicitly disabled in config", _SERVICE_NAME)
        return

    cfg = app[APP_CONFIG_KEY]
    s3_cfg = cfg[_SERVICE_NAME]
    s3_access_key = s3_cfg["access_key"]
    s3_endpoint = s3_cfg["endpoint"]
    s3_secret_key = s3_cfg["secret_key"]
    s3_bucket = s3_cfg["bucket_name"]
    s3_secure = s3_cfg["secure"]

    secure = s3_secure == 1

    s3_client = S3Client(s3_endpoint, s3_access_key, s3_secret_key, secure=secure)
    s3_client.create_bucket(s3_bucket)

    app[APP_S3_KEY] = s3_client



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

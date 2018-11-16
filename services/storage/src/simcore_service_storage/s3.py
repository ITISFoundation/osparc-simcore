""" Module to access s3 service

"""
import logging
from pathlib import Path
from typing import Dict

from aiohttp import web

from s3wrapper.s3_client import S3Client

from .dsm import DataStorageManager
from .settings import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY, APP_DSM_KEY,
                       APP_DSM_THREADPOOL)

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

    s3_client = S3Client(s3_endpoint, s3_access_key, s3_secret_key)
    s3_client.create_bucket(s3_bucket)

    main_cfg = cfg["main"]
    python27_exec = Path(main_cfg["python2"]) / "bin" / "python2"

    engine = app.get(APP_DB_ENGINE_KEY)
    assert engine
    loop = app.loop
    pool = app.get(APP_DSM_THREADPOOL)
    dsm = DataStorageManager(s3_client, python27_exec, engine, loop, pool, s3_bucket)

    app[APP_DSM_KEY] = dsm

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

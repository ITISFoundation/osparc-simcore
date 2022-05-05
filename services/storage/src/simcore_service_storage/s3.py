""" Module to access s3 service

"""
import logging
from typing import Dict

from aiohttp import web
from tenacity import before_sleep_log, retry, stop_after_attempt, wait_fixed
from pydantic import AnyUrl, parse_obj_as

from .constants import APP_CONFIG_KEY, APP_S3_KEY
from .s3wrapper.s3_client import MinioClientWrapper
from .settings import Settings
from .utils import RETRY_COUNT, RETRY_WAIT_SECS

log = logging.getLogger(__name__)


async def _setup_s3_bucket(app):
    log.debug("setup %s.setup.cleanup_ctx", __name__)

    # setup
    s3_client = app[APP_S3_KEY]
    cfg: Settings = app[APP_CONFIG_KEY]

    @retry(
        wait=wait_fixed(RETRY_WAIT_SECS),
        stop=stop_after_attempt(RETRY_COUNT),
        before_sleep=before_sleep_log(log, logging.WARNING),
        reraise=True,
    )
    async def do_create_bucket():
        log.debug("Creating bucket: %s", cfg.STORAGE_S3.json(indent=2))
        s3_client.create_bucket(cfg.STORAGE_S3.S3_BUCKET_NAME)

    try:
        await do_create_bucket()
    except Exception:  # pylint: disable=broad-except
        log.exception("Impossible to create s3 bucket. Stoping")

    # ok, failures_count = False, 0
    # while not ok:
    #     try:
    #         s3_client.create_bucket(s3_bucket)
    #         ok = True
    #     except Exception: # pylint: disable=W0703
    #         failures_count +=1
    #         if failures_count>RETRY_COUNT:
    #             log.exception("")
    #             raise
    #         await asyncio.sleep(RETRY_WAIT_SECS)
    yield

    # tear-down
    log.debug("tear-down %s.setup.cleanup_ctx", __name__)


def _minio_client_endpint(s3_endpoint: str) -> str:
    # Minio client adds http and https based on the secure paramenter
    # provided at construction time, already including the schema
    # will cause issues, encoding url to HOST:PORT
    url = parse_obj_as(AnyUrl, s3_endpoint)
    return f"{url.host}:{url.port}"


def setup_s3(app: web.Application):
    """minio/s3 service setup"""

    log.debug("Setting up %s ...", __name__)
    STORAGE_DISABLE_SERVICES = app[APP_CONFIG_KEY].STORAGE_DISABLE_SERVICES

    if "s3" in STORAGE_DISABLE_SERVICES:
        log.warning("Service '%s' explicitly disabled in config", "s3")
        return

    cfg = app[APP_CONFIG_KEY]

    s3_client = MinioClientWrapper(
        _minio_client_endpint(cfg.STORAGE_S3.S3_ENDPOINT),
        cfg.STORAGE_S3.S3_ACCESS_KEY,
        cfg.STORAGE_S3.S3_SECRET_KEY,
        secure=cfg.STORAGE_S3.S3_SECURE,
    )
    app[APP_S3_KEY] = s3_client

    app.cleanup_ctx.append(_setup_s3_bucket)


def get_config_s3(app: web.Application) -> Dict:
    cfg = app[APP_CONFIG_KEY].STORAGE_S3
    return cfg

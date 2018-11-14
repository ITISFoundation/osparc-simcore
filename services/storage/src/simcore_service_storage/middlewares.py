from pathlib import Path

from aiohttp.web import middleware

from s3wrapper.s3_client import S3Client

from .dsm import DataStorageManager
from .settings import (APP_CONFIG_KEY, APP_DB_ENGINE_KEY, APP_DSM_THREADPOOL,
                       RQT_DSM_KEY)


@middleware
async def dsm_middleware(request, handler):
    # TODO: move below code to application level into dsm setup because this might be slow
    cfg = request.app[APP_CONFIG_KEY]

    s3_cfg = cfg["s3"]
    s3_access_key = s3_cfg["access_key"]
    s3_endpoint = s3_cfg["endpoint"]
    s3_secret_key = s3_cfg["secret_key"]
    s3_bucket = s3_cfg["bucket_name"]

    s3_client = S3Client(s3_endpoint, s3_access_key, s3_secret_key)
    s3_client.create_bucket(s3_bucket)

    main_cfg = cfg["main"]
    python27_exec = Path(main_cfg["python2"]) / "bin" / "python2"

    engine = request.app.get(APP_DB_ENGINE_KEY)
    loop = request.app.loop
    pool = request.app.get(APP_DSM_THREADPOOL)
    dsm = DataStorageManager(s3_client, python27_exec, engine, loop, pool, s3_bucket)

    request[RQT_DSM_KEY] = dsm
    try:
        resp = await handler(request)
    finally:
        del request[RQT_DSM_KEY]

    return resp

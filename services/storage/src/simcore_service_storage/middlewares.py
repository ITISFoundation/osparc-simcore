from aiohttp.web import middleware

from s3wrapper.s3_client import S3Client

from .dsm import DataStorageManager
from .settings import APP_CONFIG_KEY, APP_DB_ENGINE_KEY, RQT_DSM_KEY


@middleware
async def dsm_middleware(request, handler):
    cfg = request.app[APP_CONFIG_KEY]

    # db_cfg = cfg["postgres"]

    # db_endpoint = 'postgresql://{user}:{password}@{host}:{port}/{database}'.format(
    #         database=db_cfg["database"],
    #         user=db_cfg["user"],
    #         password=db_cfg["password"],
    #         host=db_cfg["host"],
    #         port=db_cfg["port"])


    s3_cfg = cfg["s3"]
    s3_access_key = s3_cfg["access_key"]
    s3_endpoint = s3_cfg["endpoint"]
    s3_secret_key = s3_cfg["secret_key"]

    s3_client = S3Client(s3_endpoint, s3_access_key, s3_secret_key)

    main_cfg = cfg["main"]
    python27_exec = main_cfg["python2"]

    engine = request.app.get(APP_DB_ENGINE_KEY)

    dsm = DataStorageManager(s3_client, python27_exec, engine)

    request[RQT_DSM_KEY] = dsm
    try:
        resp = await handler(request)
    finally:
        del request[RQT_DSM_KEY]

    return resp

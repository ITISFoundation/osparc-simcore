from models_library.api_schemas_storage.zipping_tasks import ZipTask
from servicelib.rabbitmq import RPCRouter

router = RPCRouter()


@router.expose()
async def start_zipping(paths: list[str]) -> ZipTask:
    return ZipTask(msg="".join(paths))

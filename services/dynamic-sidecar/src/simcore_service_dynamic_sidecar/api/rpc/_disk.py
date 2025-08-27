from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...services import disk

router = RPCRouter()


@router.expose()
async def delete_reserved_disk(_: FastAPI) -> None:
    disk.delete_reserved_disk()

from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...services import disk

router = RPCRouter()


@router.expose()
async def free_reserved_disk_space(_: FastAPI) -> None:
    disk.remove_reserved_disk_space()

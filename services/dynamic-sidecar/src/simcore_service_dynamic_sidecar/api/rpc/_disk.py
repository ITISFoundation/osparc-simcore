from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...services.disk import remove_reserved_disk_space

router = RPCRouter()


@router.expose()
async def free_reserved_disk_space(_: FastAPI) -> None:
    remove_reserved_disk_space()

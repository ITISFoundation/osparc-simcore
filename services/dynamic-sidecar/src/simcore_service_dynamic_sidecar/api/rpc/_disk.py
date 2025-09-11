from fastapi import FastAPI
from servicelib.rabbitmq import RPCRouter

from ...services import disk

router = RPCRouter()


@router.expose()
async def free_reserved_disk_space(_: FastAPI) -> None:
    """Frees up reserved disk space"""
    disk.free_reserved_disk_space()

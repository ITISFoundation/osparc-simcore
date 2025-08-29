from fastapi import APIRouter, status

from ...services import disk

router = APIRouter()


@router.post("/disk/reserved:free", status_code=status.HTTP_204_NO_CONTENT)
async def free_reserved_disk_space() -> None:
    """Frees up reserved disk space"""
    disk.free_reserved_disk_space()

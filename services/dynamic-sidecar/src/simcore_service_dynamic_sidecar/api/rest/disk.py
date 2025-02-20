from fastapi import APIRouter, status

from ...services import disk

router = APIRouter()


@router.post(
    "/disk/reserved:free",
    summary="Frees up reserved disk space",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def free_reserved_disk_space() -> None:
    disk.remove_reserved_disk_space()

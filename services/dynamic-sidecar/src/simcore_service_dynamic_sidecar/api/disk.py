from fastapi import APIRouter, status

from ..core.reserved_space import remove_reserved_disk_space

router = APIRouter()


@router.post(
    "/disk/reserved:free",
    summary="Frees up reserved disk space",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def free_reserved_disk_space() -> None:
    remove_reserved_disk_space()

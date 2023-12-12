from fastapi import APIRouter, status

from ..core.emergency_space import remove_emergency_disk_space

router = APIRouter()


@router.post(
    "/disk/emergency:free",
    summary="Frees up emergency disk space",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def free_emergency_disk_space() -> None:
    remove_emergency_disk_space()

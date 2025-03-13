from pathlib import Path

from fastapi import FastAPI
from models_library.projects_nodes_io import LocationID
from models_library.users import UserID
from pydantic import ByteSize

from ...dsm import get_dsm_provider


async def compute_path_size(
    app: FastAPI, user_id: UserID, location_id: LocationID, path: Path
) -> ByteSize:
    dsm = get_dsm_provider(app).get(location_id)
    return await dsm.compute_path_size(user_id, path=path)

from typing import Annotated

from fastapi import Depends, FastAPI
from models_library.projects_nodes_io import LocationID
from servicelib.fastapi.dependencies import get_app

from ....dsm import get_dsm_provider
from ....dsm_factory import BaseDataManager, DataManagerProvider


def get_data_manager_provider(
    app: Annotated[FastAPI, Depends(get_app)],
) -> DataManagerProvider:
    return get_dsm_provider(app)


async def get_data_manager(
    location_id: LocationID,
    data_manager_provider: Annotated[
        DataManagerProvider, Depends(get_data_manager_provider)
    ],
) -> BaseDataManager:
    return data_manager_provider.get(location_id)

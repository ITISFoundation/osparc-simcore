from typing import Annotated

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ...services_rpc.resource_usage_tracker import ResourceUsageTrackerClient


async def get_resource_usage_tracker_client(
    app: Annotated[FastAPI, Depends(get_app)]
) -> ResourceUsageTrackerClient:
    return ResourceUsageTrackerClient.get_from_app_state(app=app)

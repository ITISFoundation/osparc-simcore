from typing import Annotated, cast

from fastapi import Depends, FastAPI
from servicelib.fastapi.dependencies import get_app

from ...services_rpc.resource_usage_tracker import ResourceUsageTrackerClient


async def get_resource_usage_tracker_client(
    app: Annotated[FastAPI, Depends(get_app)]
) -> ResourceUsageTrackerClient:
    assert app.state.resource_usage_tracker_rpc_client  # nosec
    return cast(ResourceUsageTrackerClient, app.state.resource_usage_tracker_rpc_client)

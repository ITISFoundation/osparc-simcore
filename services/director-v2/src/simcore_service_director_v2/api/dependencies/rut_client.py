from typing import cast

from fastapi import Request

from ...modules.resource_usage_tracker_client import ResourceUsageTrackerClient


def get_rut_client(request: Request) -> ResourceUsageTrackerClient:
    return cast(
        ResourceUsageTrackerClient,
        ResourceUsageTrackerClient.get_from_state(request.app),
    )

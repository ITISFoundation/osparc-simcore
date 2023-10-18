from typing import cast

from fastapi import Request

from ...modules.resource_usage_client import ResourceUsageClient


def get_rut_client(request: Request) -> ResourceUsageClient:
    return cast(ResourceUsageClient, ResourceUsageClient.get_from_state(request.app))

from fastapi import Request

from ...services.registry import RegistryClient


def get_registry_client(request: Request) -> RegistryClient:
    return request.app.state.registry_client

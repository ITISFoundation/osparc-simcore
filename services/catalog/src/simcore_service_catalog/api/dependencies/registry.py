from typing import Optional

from fastapi import Request

from ...services.registry import RegistryClient


def get_registry_client(request: Request) -> Optional[RegistryClient]:
    return request.app.state.registry_client

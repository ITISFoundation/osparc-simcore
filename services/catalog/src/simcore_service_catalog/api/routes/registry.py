from typing import Dict, List

from fastapi import APIRouter, Depends
from models_library.services import KEY_RE, VERSION_RE
from pydantic import constr

from ...services.registry import RegistryClient
from ..dependencies.registry import get_registry_client

router = APIRouter()


@router.get("/{service_key:path}/{service_version}:labels")
async def get_service_labels(
    service_key: constr(regex=KEY_RE),
    service_version: constr(regex=VERSION_RE),
    registry_client: RegistryClient = Depends(get_registry_client),
) -> Dict[str, str]:
    return await registry_client.get_labels(service_key, service_version)


@router.get("/repository")
async def get_registry_repositories(
    registry_client: RegistryClient = Depends(get_registry_client),
) -> Dict[str, str]:
    return await registry_client.get_repositories()


@router.get("/{service_key:path}:tags")
async def get_service_tags(
    service_key: constr(regex=KEY_RE),
    registry_client: RegistryClient = Depends(get_registry_client),
) -> List[str]:
    return await registry_client.get_tags(service_key)

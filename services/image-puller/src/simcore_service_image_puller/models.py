from asyncio import Lock
from dataclasses import dataclass

from httpx import AsyncClient

from .settings import ImagePullerSettings


@dataclass
class AppState:
    settings: ImagePullerSettings
    worker_lock: Lock
    catalog_client: AsyncClient

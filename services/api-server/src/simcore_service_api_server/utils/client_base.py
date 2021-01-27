from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import FastAPI


@dataclass
class BaseServiceClientApi:
    """
    - wrapper around thin-client to simplify service's API calls
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception
    - helpers to create a unique client instance per application and service
    """

    client: httpx.AsyncClient
    service_name: str = ""
    health_check_path: str = "/"

    @classmethod
    def create(cls, app: FastAPI, **kwargs):
        if not hasattr(cls, "state_attr_name"):
            cls.state_attr_name = f"client_{cls.__name__.lower()}"
        instance = cls(**kwargs)
        setattr(app.state, cls.state_attr_name, instance)
        return instance

    @classmethod
    def get_instance(cls, app: FastAPI) -> Optional["BaseServiceClientApi"]:
        try:
            obj = getattr(app.state, cls.state_attr_name)
        except AttributeError:
            return None
        return obj

    async def aclose(self):
        await self.client.aclose()

    async def is_responsive(self) -> bool:
        try:
            resp = await self.client.get(self.health_check_path)
            resp.raise_for_status()
            return True
        except httpx.HTTPStatusError:
            return False

from dataclasses import dataclass
from typing import Optional

import httpx
from fastapi import FastAPI


@dataclass
class BaseServiceClientApi:
    """
    - wrapper around thin-client to simplify service's API
    - sets endspoint upon construction
    - MIME type: application/json
    - processes responses, returning data or raising formatted HTTP exception

    """
    client: httpx.AsyncClient
    service_name: str = ""

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

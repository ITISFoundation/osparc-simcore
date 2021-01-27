from typing import Any, Dict

import yaml

from .utils import assemble_container_name
from .settings import ServiceSidecarSettings


class AsyncStore:
    """Define custom storage abstraction for easy future extention"""

    __slots__ = ("_storage", "_settings")

    KEY = "compose_spec"  # default key for all actions

    def __init__(self, settings: ServiceSidecarSettings):
        self._storage: Dict[str, Any] = {}
        self._settings: ServiceSidecarSettings = settings

    async def get(self, default=None) -> Any:
        return self._storage.get(AsyncStore.KEY, default)

    async def update(self, value: Any) -> None:
        self._storage[AsyncStore.KEY] = value

    async def get_container_names(self):
        """Parses the stored spec and returns the container names"""
        # TODO: refactor to add caching here
        compose_file_content = await self.get()
        if compose_file_content is None:
            return []

        parsed_compose_spec = yaml.safe_load(compose_file_content)
        return [
            assemble_container_name(self._settings, service)
            for service in parsed_compose_spec["services"]
        ]
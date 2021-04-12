from typing import Any, Dict, List, Optional

from .settings import ServiceSidecarSettings
from .utils import assemble_container_names, validate_compose_spec


class SharedStore:
    """Define custom storage abstraction for easy future extension"""

    __slots__ = ("_storage", "_settings", "_is_pulling_containsers")

    _K_COMPOSE_SPEC = "compose_spec"
    _K_CONTAINER_NAMES = "container_names"

    def __set_as_compose_spec_none(self):
        self._storage[self._K_COMPOSE_SPEC] = None
        self._storage[self._K_CONTAINER_NAMES] = []

    def __init__(self, settings: ServiceSidecarSettings):
        self._storage: Dict[str, Any] = {}
        self._settings: ServiceSidecarSettings = settings
        self._is_pulling_containsers: bool = False
        self.__set_as_compose_spec_none()

    def put_spec(self, compose_file_content: Optional[str]) -> None:
        if compose_file_content is None:
            self.__set_as_compose_spec_none()
            return

        self._storage[self._K_COMPOSE_SPEC] = validate_compose_spec(
            settings=self._settings, compose_file_content=compose_file_content
        )
        self._storage[self._K_CONTAINER_NAMES] = assemble_container_names(
            self._storage[self._K_COMPOSE_SPEC]
        )

    def get_spec(self) -> Optional[Any]:
        return self._storage.get(self._K_COMPOSE_SPEC)

    def get_container_names(self) -> List[str]:
        return self._storage[self._K_CONTAINER_NAMES]

    @property
    def is_pulling_containsers(self) -> bool:
        return self._is_pulling_containsers

    def set_is_pulling_containsers(self) -> None:
        self._is_pulling_containsers = True

    def unset_is_pulling_containsers(self) -> None:
        self._is_pulling_containsers = False

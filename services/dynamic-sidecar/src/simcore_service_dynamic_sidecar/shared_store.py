from typing import List, Optional

from pydantic import BaseModel, Field, PrivateAttr

from .settings import DynamicSidecarSettings
from .utils import assemble_container_names, validate_compose_spec


class SharedStore(BaseModel):
    _settings: DynamicSidecarSettings = PrivateAttr()

    compose_spec: Optional[str] = Field(
        None, description="stores the stringified compose spec"
    )
    container_names: List[str] = Field(
        [], description="stores the container names from the compose_spec"
    )
    is_pulling_containsers: bool = Field(
        False, description="set to True while the containers are being pulled"
    )

    def __init__(self, settings: DynamicSidecarSettings):
        self._settings = settings
        super().__init__()

    def put_spec(self, compose_file_content: Optional[str]) -> None:
        """Validates the spec before storing it and updated the container_names list"""
        if compose_file_content is None:
            self.compose_spec = None
            self.container_names = []
            return

        self.compose_spec = validate_compose_spec(
            settings=self._settings, compose_file_content=compose_file_content
        )
        self.container_names = assemble_container_names(self.compose_spec)

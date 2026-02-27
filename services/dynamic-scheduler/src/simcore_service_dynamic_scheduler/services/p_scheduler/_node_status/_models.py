from enum import auto

from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, model_validator

type ServiceName = str


class ComponentPresence(StrAutoEnum):
    ABSENT = auto()  # not present
    STARTING = auto()  # being created / initializing
    RUNNING = auto()  # fully operational
    FAILED = auto()  # error state


class ServicesPresence(BaseModel):
    legacy: ComponentPresence | None = None
    dy_sidecar: ComponentPresence | None = None
    dy_proxy: ComponentPresence | None = None

    @model_validator(mode="after")
    def _check_mutually_exclusive_groups(self) -> "ServicesPresence":
        if not self.legacy and not self.dy_sidecar and not self.dy_proxy:
            # all absent → valid, no services
            return self

        has_legacy = self.legacy is not None
        has_new_style = self.dy_sidecar is not None or self.dy_proxy is not None

        if has_legacy and has_new_style:
            msg = f"Cannot have both legacy and new-style (dy_sidecar/dy_proxy) entries {self}"
            raise ValueError(msg)

        if not has_legacy and not has_new_style:
            msg = f"Must provide either a legacy or new-style (dy_sidecar/dy_proxy) entry {self}"
            raise ValueError(msg)

        return self

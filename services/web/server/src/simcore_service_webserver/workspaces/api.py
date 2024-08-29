# mypy: disable-error-code=truthy-function
from ._workspaces_api import get_workspace

assert get_workspace  # nosec

__all__: tuple[str, ...] = ("get_workspace",)

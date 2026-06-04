from . import _client as client
from ._setup import registry_lifespan

__all__: tuple[str, ...] = (
    "client",
    "registry_lifespan",
)

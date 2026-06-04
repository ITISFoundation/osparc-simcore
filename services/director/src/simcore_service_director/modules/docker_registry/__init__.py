from . import _client as client
from ._setup import configure_registry_lifespans, registry_lifespan

__all__: tuple[str, ...] = (
    "client",
    "configure_registry_lifespans",
    "registry_lifespan",
)

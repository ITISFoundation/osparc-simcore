from ._permalink_api import ProjectPermalink
from ._permalink_api import register_factory as register_permalink_factory

__all__: tuple[str, ...] = (
    "ProjectPermalink",
    "register_permalink_factory",
)

# nopycln: file

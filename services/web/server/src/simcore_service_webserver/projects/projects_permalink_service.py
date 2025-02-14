from ._permalink_service import ProjectPermalink
from ._permalink_service import register_factory as register_permalink_factory

__all__: tuple[str, ...] = (
    "ProjectPermalink",
    "register_permalink_factory",
)

# nopycln: file

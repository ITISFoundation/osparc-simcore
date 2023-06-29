# NOTE: we will slowly move heere projects_api.py


from ._permalink_api import ProjectPermalink
from ._permalink_api import register_factory as register_permalink_factory

__all__: tuple[str, ...] = (
    "register_permalink_factory",
    "ProjectPermalink",
)


# nopycln: file

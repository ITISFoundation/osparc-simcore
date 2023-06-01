# NOTE: we will slowly move heere projects_api.py


from ._permalink import ProjectPermalink
from ._permalink import register_factory as register_permalink_factory

__all__: tuple[str, ...] = (
    "register_permalink_factory",
    "ProjectPermalink",
)


# nopycln: file

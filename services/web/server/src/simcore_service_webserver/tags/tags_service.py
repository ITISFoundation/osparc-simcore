# Exceptions
# Functions
from ._service import (
    create_tag,
    delete_tag,
    list_tag_groups,
    list_tags,
    share_tag_with_group,
    unshare_tag_with_group,
    update_tag,
)
from .errors import (
    InsufficientTagShareAccessError,
    ShareTagWithEveryoneNotAllowedError,
    ShareTagWithProductGroupNotAllowedError,
    TagsPermissionError,
)

# Models
from .schemas import (
    TagAccessRights,
    TagCreate,
    TagGet,
    TagGroupCreate,
    TagGroupGet,
    TagGroupPathParams,
    TagPathParams,
    TagRequestContext,
    TagUpdate,
)

__all__: tuple[str, ...] = (
    # exceptions
    "InsufficientTagShareAccessError",
    "ShareTagWithEveryoneNotAllowedError",
    "ShareTagWithProductGroupNotAllowedError",
    # models
    "TagAccessRights",
    "TagCreate",
    "TagGet",
    "TagGroupCreate",
    "TagGroupGet",
    "TagGroupPathParams",
    "TagPathParams",
    "TagRequestContext",
    "TagUpdate",
    "TagsPermissionError",
    # functions
    "create_tag",
    "delete_tag",
    "list_tag_groups",
    "list_tags",
    "share_tag_with_group",
    "unshare_tag_with_group",
    "update_tag",
)  # nopycln: file

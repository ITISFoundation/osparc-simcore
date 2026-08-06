"""Domain models for tags - re-exports from schemas.py."""

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
)

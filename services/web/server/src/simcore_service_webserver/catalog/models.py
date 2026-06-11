"""Catalog public facade for models per DESIGN.md §133-152."""

from ._models import ServiceKeyVersionDict

__all__: tuple[str, ...] = (
    # models
    "ServiceKeyVersionDict",
)

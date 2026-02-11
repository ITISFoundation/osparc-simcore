from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from typing import Any, Self, TypeVar

from sqlalchemy.engine.row import Row

ModelType = TypeVar("ModelType")


class FromRowMixin:
    """Mixin to allow instance construction from database row objects"""

    @classmethod
    def from_row(cls, row: Any) -> Self:
        """Creates an instance from a database row.

        Supports both Row objects and mapping-like objects.
        """
        assert is_dataclass(cls)  # nosec

        if isinstance(row, Row):
            mapping = row._asdict()
        elif isinstance(row, Mapping):
            mapping = row
        else:
            msg = f"Row must be a Row or Mapping type, got {type(row)}"
            raise TypeError(msg)

        field_names = [f.name for f in fields(cls)]
        return cls(**{k: v for k, v in mapping.items() if k in field_names})

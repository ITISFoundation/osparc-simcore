from dataclasses import fields, is_dataclass
from typing import TypeVar

from aiopg.sa.result import RowProxy

ModelType = TypeVar("ModelType")


class FromRowMixin:
    """Mixin to allow instance construction from aiopg.sa.result.RowProxy"""

    @classmethod
    def from_row(cls: type[ModelType], row: RowProxy) -> ModelType:
        assert is_dataclass(cls)  # nosec
        field_names = [f.name for f in fields(cls)]
        return cls(**{k: v for k, v in row.items() if k in field_names})  # type: ignore[return-value]

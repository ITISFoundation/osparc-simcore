from typing import TypeVar

from aiopg.sa.result import RowProxy

ModelType = TypeVar("ModelType")


class FromRowMixin:
    """Mixin to allow instance construction from aiopg.sa.result.RowProxy"""

    @classmethod
    def from_row(cls: type[ModelType], row: RowProxy) -> ModelType:
        return cls(**dict(row.items()))

from collections.abc import ItemsView, Iterable, Iterator, KeysView, ValuesView
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, RootModel

DictKey = TypeVar("DictKey")
DictValue = TypeVar("DictValue")


class DictModel(RootModel[dict[DictKey, DictValue]], Generic[DictKey, DictValue]):
    root: dict[DictKey, DictValue]

    def __getitem__(self, k: DictKey) -> DictValue:
        return self.root.__getitem__(k)

    def __setitem__(self, k: DictKey, v: DictValue) -> None:
        self.root.__setitem__(k, v)

    def items(self) -> ItemsView[DictKey, DictValue]:
        return self.root.items()

    def keys(self) -> KeysView[DictKey]:
        return self.root.keys()

    def values(self) -> ValuesView[DictValue]:
        return self.root.values()

    def update(self, *s: Iterable[tuple[DictKey, DictValue]]) -> None:
        return self.root.update(*s)

    def __iter__(self) -> Iterator[DictKey]:  # type: ignore
        return self.root.__iter__()

    def get(self, key: DictKey, default: DictValue | None = None):
        return self.root.get(key, default)

    def setdefault(self, key: DictKey, default: DictValue):
        return self.root.setdefault(key, default)

    def __len__(self) -> int:
        return self.root.__len__()


DataT = TypeVar("DataT")


class ListModel(RootModel[list[DataT]], Generic[DataT]):
    root: list[DataT]

    def __iter__(self):
        return iter(self.root)

    def __getitem__(self, item):
        return self.root[item]

    def __len__(self):
        return len(self.root)


class Envelope(BaseModel, Generic[DataT]):
    data: DataT | None = None
    error: Any | None = None

    @classmethod
    def from_data(cls, obj: Any) -> "Envelope":
        return cls.model_validate({"data": obj})

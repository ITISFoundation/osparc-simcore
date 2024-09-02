from collections.abc import ItemsView, Iterable, Iterator, KeysView, ValuesView
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, RootModel

DictKey = TypeVar("DictKey")
DictValue = TypeVar("DictValue")


class DictModel(RootModel[dict[DictKey, DictValue]], Generic[DictKey, DictValue]):
    def __getitem__(self, k: DictKey) -> DictValue:
        return self.__root__.__getitem__(k)

    def __setitem__(self, k: DictKey, v: DictValue) -> None:
        self.__root__.__setitem__(k, v)

    def items(self) -> ItemsView[DictKey, DictValue]:
        return self.__root__.items()

    def keys(self) -> KeysView[DictKey]:
        return self.__root__.keys()

    def values(self) -> ValuesView[DictValue]:
        return self.__root__.values()

    def update(self, *s: Iterable[tuple[DictKey, DictValue]]) -> None:
        return self.__root__.update(*s)

    def __iter__(self) -> Iterator[DictKey]:  # type: ignore
        return self.__root__.__iter__()

    def get(self, key: DictKey, default: DictValue | None = None):
        return self.__root__.get(key, default)

    def setdefault(self, key: DictKey, default: DictValue):
        return self.__root__.setdefault(key, default)

    def __len__(self) -> int:
        return self.__root__.__len__()


DataT = TypeVar("DataT")


class ListModel(RootModel[list[DataT]], Generic[DataT]):
    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __len__(self):
        return len(self.__root__)


class Envelope(BaseModel, Generic[DataT]):
    data: DataT | None = None
    error: Any | None = None

    @classmethod
    def from_data(cls, obj: Any) -> "Envelope":
        return cls.model_validate({"data": obj})

from typing import (
    Any,
    Generic,
    ItemsView,
    Iterable,
    Iterator,
    KeysView,
    TypeVar,
    ValuesView,
)

from pydantic import validator
from pydantic.generics import GenericModel

DictKey = TypeVar("DictKey")
DictValue = TypeVar("DictValue")


class DictModel(GenericModel, Generic[DictKey, DictValue]):
    __root__: dict[DictKey, DictValue]

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

    def __iter__(self) -> Iterator[DictKey]:
        return self.__root__.__iter__()

    def get(self, key: DictKey, default: DictValue | None = None):
        return self.__root__.get(key, default)

    def setdefault(self, key: DictKey, default: DictValue):
        return self.__root__.setdefault(key, default)

    def __len__(self) -> int:
        return self.__root__.__len__()


DataT = TypeVar("DataT")


class ListModel(GenericModel, Generic[DataT]):
    __root__: list[DataT]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __len__(self):
        return len(self.__root__)


class Envelope(GenericModel, Generic[DataT]):
    data: DataT | None = None
    error: Any | None = None

    @classmethod
    def parse_data(cls, obj):
        return cls.parse_obj({"data": obj})

    @validator("data", pre=True)
    @classmethod
    def empty_dict_is_none(cls, v):
        if v == {}:
            return None
        return v

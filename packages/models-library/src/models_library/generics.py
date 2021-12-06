from typing import (
    Any,
    Dict,
    Generic,
    ItemsView,
    Iterator,
    KeysView,
    List,
    Optional,
    TypeVar,
    ValuesView,
)

from pydantic.generics import GenericModel

DictKey = TypeVar("DictKey")
DictValue = TypeVar("DictValue")


class DictModel(GenericModel, Generic[DictKey, DictValue]):
    __root__: Dict[DictKey, DictValue]

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

    def __iter__(self) -> Iterator[DictKey]:
        return self.__root__.__iter__()

    def get(self, key: DictKey, default: Optional[DictValue] = None):
        return self.__root__.get(key, default)

    def __len__(self) -> int:
        return self.__root__.__len__()


DataT = TypeVar("DataT")


class ListModel(GenericModel, Generic[DataT]):
    __root__: List[DataT]

    def __iter__(self):
        return iter(self.__root__)

    def __getitem__(self, item):
        return self.__root__[item]

    def __len__(self):
        return len(self.__root__)


class Envelope(GenericModel, Generic[DataT]):
    data: Optional[DataT]
    error: Optional[Any]
    # TODO: this needs to be more concreate e.g. { "error": { "reason": "Invalid" , "exception": "ValueError" } }

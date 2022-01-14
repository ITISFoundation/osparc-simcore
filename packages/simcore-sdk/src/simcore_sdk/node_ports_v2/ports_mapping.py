from typing import Dict, ItemsView, Iterator, KeysView, Type, Union, ValuesView

from models_library.services import PROPERTY_KEY_RE
from pydantic import BaseModel, constr

from ..node_ports_common.exceptions import UnboundPortError
from .port import Port

PortKey: Type[str] = constr(regex=PROPERTY_KEY_RE)


class BasePortsMapping(BaseModel):
    __root__: Dict[PortKey, Port]

    def __getitem__(self, key: Union[int, PortKey]) -> Port:
        if isinstance(key, int):
            if key < len(self.__root__):
                key = list(self.__root__.keys())[key]
        if not key in self.__root__:
            raise UnboundPortError(key)
        assert isinstance(key, str)  # nosec
        return self.__root__[key]

    def __iter__(self) -> Iterator[PortKey]:
        return iter(self.__root__)

    def keys(self) -> KeysView[PortKey]:
        return self.__root__.keys()

    def items(self) -> ItemsView[PortKey, Port]:
        return self.__root__.items()

    def values(self) -> ValuesView[Port]:
        return self.__root__.values()

    def __len__(self) -> int:
        return self.__root__.__len__()


class InputsList(BasePortsMapping):
    pass


class OutputsList(BasePortsMapping):
    pass

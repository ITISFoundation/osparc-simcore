from typing import Dict, Union

from models_library.services import PROPERTY_KEY_RE
from pydantic import BaseModel, constr

from ..node_ports.exceptions import UnboundPortError
from .port import Port

PortKey = constr(regex=PROPERTY_KEY_RE)


class PortsMapping(BaseModel):
    __root__: Dict[PortKey, Port]

    def __getitem__(self, key: Union[int, PortKey]) -> Port:
        if isinstance(key, int):
            if key < len(self.__root__):
                key = list(self.__root__.keys())[key]
        if not key in self.__root__:
            raise UnboundPortError(key)
        return self.__root__[key]

    def __iter__(self):
        return iter(self.__root__)

    def items(self):
        return self.__root__.items()

    def values(self):
        return self.__root__.values()

    def __len__(self):
        return self.__root__.__len__()


class InputsList(PortsMapping):
    __root__: Dict[PortKey, Port]


class OutputsList(PortsMapping):
    __root__: Dict[PortKey, Port]

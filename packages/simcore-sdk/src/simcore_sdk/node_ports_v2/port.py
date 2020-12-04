import logging
from pathlib import Path
from pprint import pformat
from typing import Dict, Optional, Tuple, Type, Union

from models_library.services import PROPERTY_KEY_RE, ServiceProperty
from pydantic import BaseModel, Field, PrivateAttr, validator

from ..node_ports.exceptions import InvalidItemTypeError, UnboundPortError
from . import port_utils
from .links import DataItemValue, DownloadLink, FileLink, ItemConcreteValue, PortLink

log = logging.getLogger(__name__)


TYPE_TO_PYTYPE: Dict[str, Type[ItemConcreteValue]] = {
    "integer": int,
    "number": float,
    "boolean": bool,
    "string": str,
}


class Port(ServiceProperty):
    key: str = Field(..., regex=PROPERTY_KEY_RE)
    widget: Optional[Dict] = None

    value: Optional[DataItemValue]

    _py_value_type: Tuple[Type[ItemConcreteValue]] = PrivateAttr()
    _py_value_converter: Type[ItemConcreteValue] = PrivateAttr()
    _node_ports = PrivateAttr()

    @validator("value", always=True)
    @classmethod
    def ensure_value(cls, v, values):
        if "property_type" in values and port_utils.is_file_type(
            values["property_type"]
        ):
            if v is not None and not isinstance(v, (FileLink, DownloadLink, PortLink)):
                raise ValueError(
                    f"[{values['property_type']}] must follow {FileLink.schema()}, {DownloadLink.schema()} or {PortLink.schema()}"
                )
        elif v is None and values.get("default_value"):
            return values["default_value"]
        return v

    def __init__(self, **data):
        super().__init__(**data)
        # let's define the converter
        self._py_value_type = (
            (Path, str)
            if port_utils.is_file_type(self.property_type)
            else (TYPE_TO_PYTYPE[self.property_type])
        )
        self._py_value_converter = (
            Path
            if port_utils.is_file_type(self.property_type)
            else TYPE_TO_PYTYPE[self.property_type]
        )

    async def get(self) -> ItemConcreteValue:
        log.debug(
            "getting %s[%s] with value %s",
            self.key,
            self.property_type,
            pformat(self.value),
        )

        if self.value is None:
            return None

        value = None
        if isinstance(self.value, PortLink):
            # this is a link to another node
            value = await port_utils.get_value_from_link(
                # pylint: disable=protected-access
                self.key,
                self.value,
                self.file_to_key_map,
                self._node_ports._node_ports_creator_cb,
            )
        elif isinstance(self.value, FileLink):
            # this is a link from storage
            value = await port_utils.pull_file_from_store(
                self.key, self.file_to_key_map, self.value
            )
        elif isinstance(self.value, DownloadLink):
            # this is a downloadable link
            value = await port_utils.pull_file_from_download_link(
                self.key, self.file_to_key_map, self.value
            )
        else:
            # this is directly the value
            value = self.value

        return self._py_value_converter(value)

    async def set(self, new_value: ItemConcreteValue):
        log.debug(
            "setting %s[%s] with value %s", self.key, self.property_type, new_value
        )
        # convert the concrete value to a data value
        data_value = self._py_value_converter(new_value)

        if not isinstance(data_value, self._py_value_type):
            raise InvalidItemTypeError(self.property_type, new_value)

        if port_utils.is_file_type(self.property_type):
            if not data_value.exists() or not data_value.is_file():
                raise InvalidItemTypeError(self.property_type, new_value)
            data_value: FileLink = await port_utils.push_file_to_store(data_value)

        self.value = data_value
        await self._node_ports.save_to_db_cb(self._node_ports)


PortKey = str


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


class InputsList(PortsMapping):
    __root__: Dict[PortKey, Port]


class OutputsList(PortsMapping):
    __root__: Dict[PortKey, Port]

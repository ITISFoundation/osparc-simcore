import logging
from pathlib import Path
from pprint import pformat
from typing import Any, Dict, Optional, Tuple, Type

from models_library.services import PROPERTY_KEY_RE, ServiceProperty
from pydantic import Field, PrivateAttr, validator

from ..node_ports.exceptions import InvalidItemTypeError
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
    widget: Optional[Dict[str, Any]] = None

    value: Optional[DataItemValue]

    _py_value_type: Tuple[Type[ItemConcreteValue]] = PrivateAttr()
    _py_value_converter: Type[ItemConcreteValue] = PrivateAttr()
    _node_ports = PrivateAttr()
    _used_default_value: bool = PrivateAttr(False)

    @validator("value", always=True)
    @classmethod
    def ensure_value(cls, v: DataItemValue, values: Dict[str, Any]) -> DataItemValue:
        if "property_type" in values and port_utils.is_file_type(
            values["property_type"]
        ):
            if v is not None and not isinstance(v, (FileLink, DownloadLink, PortLink)):
                raise ValueError(
                    f"[{values['property_type']}] must follow {FileLink.schema()}, {DownloadLink.schema()} or {PortLink.schema()}"
                )
        return v

    def __init__(self, **data: Any):
        super().__init__(**data)

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
        if (
            self.value is None
            and self.default_value is not None
            and not port_utils.is_file_type(self.property_type)
        ):
            self.value = self.default_value
            self._used_default_value = True

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

    async def set(self, new_value: ItemConcreteValue) -> None:
        log.debug(
            "setting %s[%s] with value %s", self.key, self.property_type, new_value
        )
        final_value: Optional[DataItemValue] = None
        if new_value is not None:
            # convert the concrete value to a data value
            converted_value: ItemConcreteValue = self._py_value_converter(new_value)

            if isinstance(converted_value, Path):
                if not converted_value.exists() or not converted_value.is_file():
                    raise InvalidItemTypeError(self.property_type, str(new_value))
                final_value = await port_utils.push_file_to_store(converted_value)
            else:
                final_value = converted_value

        self.value = final_value
        self._used_default_value = False
        await self._node_ports.save_to_db_cb(self._node_ports)

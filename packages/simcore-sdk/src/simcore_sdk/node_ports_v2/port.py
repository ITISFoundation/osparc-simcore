import logging
import os
from pathlib import Path
from pprint import pformat
from typing import Any, Callable, Dict, Optional, Tuple, Type

from models_library.services import PROPERTY_KEY_RE, ServiceProperty
from pydantic import AnyUrl, Field, PrivateAttr, validator

from ..node_ports_common.exceptions import InvalidItemTypeError
from . import port_utils
from .links import (
    DataItemValue,
    DownloadLink,
    FileLink,
    ItemConcreteValue,
    ItemValue,
    PortLink,
)

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

    default_value: Optional[DataItemValue] = Field(None, alias="defaultValue")
    value: Optional[DataItemValue]

    _py_value_type: Tuple[Type[ItemConcreteValue], ...] = PrivateAttr()
    _py_value_converter: Callable[[Any], ItemConcreteValue] = PrivateAttr()
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

    async def get_value(self) -> Optional[ItemValue]:
        """returns the value of the link after resolving the port links"""
        log.debug(
            "getting value of %s[%s] containing '%s'",
            self.key,
            self.property_type,
            pformat(self.value),
        )

        if isinstance(self.value, PortLink):
            # this is a link to another node
            return await port_utils.get_value_link_from_port_link(
                # pylint: disable=protected-access
                self.value,
                self._node_ports._node_ports_creator_cb,
            )
        if isinstance(self.value, FileLink):
            # let's get the download/upload link from storage
            return await port_utils.get_download_link_from_storage(
                user_id=self._node_ports.user_id,
                value=self.value,
            )

        if isinstance(self.value, DownloadLink):
            # this is a downloadable link
            return self.value.download_link

        return self.value

    async def get(self) -> Optional[ItemConcreteValue]:
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
                key=self.key,
                value=self.value,
                fileToKeyMap=self.file_to_key_map,
                node_port_creator=self._node_ports._node_ports_creator_cb,
            )
        elif isinstance(self.value, FileLink):
            # this is a link from storage
            value = await port_utils.pull_file_from_store(
                user_id=self._node_ports.user_id,
                key=self.key,
                fileToKeyMap=self.file_to_key_map,
                value=self.value,
            )
        elif isinstance(self.value, DownloadLink):
            # this is a downloadable link
            value = await port_utils.pull_file_from_download_link(
                key=self.key,
                fileToKeyMap=self.file_to_key_map,
                value=self.value,
            )
        else:
            # this is directly the value
            value = self.value
        # don't atempt conversion of None it fails
        if value is None:
            return None

        return self._py_value_converter(value)

    async def _set(self, new_value: ItemConcreteValue) -> None:
        log.debug(
            "setting %s[%s] with concrete value %s",
            self.key,
            self.property_type,
            new_value,
        )
        final_value: Optional[DataItemValue] = None
        if new_value is not None:
            # convert the concrete value to a data value
            converted_value: ItemConcreteValue = self._py_value_converter(new_value)

            def _raise_if_file_not_on_disk(path: Path) -> None:
                if not path.exists() or not path.is_file():
                    log.warning("Could not find a valid file %s", path)
                    raise InvalidItemTypeError(self.property_type, str(new_value))

            if isinstance(converted_value, Path):
                if converted_value.is_symlink():
                    symlink_target_path = Path(os.readlink(converted_value))
                    if not symlink_target_path.is_absolute():
                        # in the case of a relative symlink
                        # since the working directory is different form the
                        # one in which the symlink is placed,
                        # it must be transfromed to an absolute path
                        symlink_target_path = (
                            converted_value.parent / symlink_target_path
                        )
                    _raise_if_file_not_on_disk(symlink_target_path)
                else:
                    _raise_if_file_not_on_disk(converted_value)
                final_value = await port_utils.push_file_to_store(
                    file=converted_value,
                    user_id=self._node_ports.user_id,
                    project_id=self._node_ports.project_id,
                    node_id=self._node_ports.node_uuid,
                )
            else:
                final_value = converted_value

        self.value = final_value
        self._used_default_value = False

    async def set(self, new_value: ItemConcreteValue) -> None:
        """sets a value to the port, by default it is also stored in the database"""
        await self._set(new_value)
        await self._node_ports.save_to_db_cb(self._node_ports)

    async def set_value(self, new_value: Optional[ItemValue]) -> None:
        """set the value on the port using a value (e.g. link for the file)"""
        log.debug(
            "setting %s[%s] with value %s", self.key, self.property_type, new_value
        )
        final_value: Optional[DataItemValue] = None
        if port_utils.is_file_type(self.property_type) and new_value is not None:
            if not isinstance(new_value, AnyUrl):
                raise InvalidItemTypeError(self.property_type, f"{new_value}")
            final_value = await port_utils.get_file_link_from_url(
                new_value,
                self._node_ports.user_id,
                self._node_ports.project_id,
                self._node_ports.node_uuid,
            )
        else:
            final_value = self._py_value_converter(new_value)

        self.value = final_value
        self._used_default_value = False
        await self._node_ports.save_to_db_cb(self._node_ports)

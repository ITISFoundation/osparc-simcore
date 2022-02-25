import logging
import os
from pathlib import Path
from pprint import pformat
from typing import Any, Callable, Dict, Optional, Tuple, Type

import jsonschema
from models_library.services import PROPERTY_KEY_RE, BaseServiceIOModel
from pydantic import AnyUrl, Field, PrivateAttr, validator

from ..node_ports_common.exceptions import (
    AbsoluteSymlinkIsNotUploadableException,
    InvalidItemTypeError,
    SymlinkToSymlinkIsNotUploadableException,
)
from . import port_utils
from .links import (
    DataItemValue,
    DownloadLink,
    FileLink,
    ItemConcreteValue,
    ItemValue,
    PortLink,
)
from .utils_schemas import jsonschema_validate_data, jsonschema_validate_schema

log = logging.getLogger(__name__)


TYPE_TO_PYTYPE: Dict[str, Type[ItemConcreteValue]] = {
    "integer": int,
    "number": float,
    "boolean": bool,
    "string": str,
}


def _check_if_symlink_is_valid(symlink: Path) -> None:
    if not symlink.is_symlink():
        return

    symlink_target_path = Path(os.readlink(symlink))
    if symlink_target_path.is_symlink():
        raise SymlinkToSymlinkIsNotUploadableException(symlink, symlink_target_path)

    if symlink_target_path.is_absolute():
        raise AbsoluteSymlinkIsNotUploadableException(symlink, symlink_target_path)


class Port(BaseServiceIOModel):
    key: str = Field(..., regex=PROPERTY_KEY_RE)
    widget: Optional[Dict[str, Any]] = None

    default_value: Optional[DataItemValue] = Field(None, alias="defaultValue")
    value: Optional[DataItemValue] = None

    _py_value_type: Tuple[Type[ItemConcreteValue], ...] = PrivateAttr()
    _py_value_converter: Callable[[Any], ItemConcreteValue] = PrivateAttr()
    _node_ports = PrivateAttr()
    _used_default_value: bool = PrivateAttr(False)

    @validator("content_schema", always=True)
    @classmethod
    def valid_content_jsonschema(cls, v):
        if v is not None:
            try:
                jsonschema_validate_schema(schema=v)
            except jsonschema.SchemaError as err:
                raise ValueError(
                    f"Invalid json-schema in 'content_schema': {err}"
                ) from err
        return v

    @validator("value", always=True)
    @classmethod
    def ensure_value(cls, v: DataItemValue, values: Dict[str, Any]) -> DataItemValue:
        if v is not None and (property_type := values.get("property_type")):
            if port_utils.is_file_type(property_type):
                if not isinstance(v, (FileLink, DownloadLink, PortLink)):
                    raise ValueError(
                        f"[{values['property_type']}] must follow "
                        f"{FileLink.schema()}, {DownloadLink.schema()} or {PortLink.schema()}"
                    )
            elif property_type == "ref_contentSchema":
                try:
                    content_schema = values["content_schema"]
                    v = jsonschema_validate_data(
                        instance=v, schema=content_schema, return_with_default=True
                    )

                except jsonschema.ValidationError as err:
                    raise ValueError(
                        f"{v} invalid against content_schema: {err.message}"
                    ) from err
            else:
                if isinstance(v, (list, dict)):
                    # TODO: SEE https://github.com/ITISFoundation/osparc-simcore/issues/2849
                    raise ValueError(
                        f"Containers as {v} currently only supported within content_schema"
                    )

        return v

    def __init__(self, **data: Any):
        super().__init__(**data)

        if port_utils.is_file_type(self.property_type):
            self._py_value_type = (Path, str)
            self._py_value_converter = Path

        elif self.property_type == "ref_contentSchema":
            self._py_value_type = (list, dict)
            self._py_value_converter = lambda v: v

        else:
            assert self.property_type in TYPE_TO_PYTYPE  # nosec

            self._py_value_type = TYPE_TO_PYTYPE[self.property_type]
            self._py_value_converter = TYPE_TO_PYTYPE[self.property_type]

            if self.value is None and self.default_value is not None:
                self.value = self.default_value
                self._used_default_value = True

        assert self._py_value_type  # nosec
        assert self._py_value_converter  # nosec

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

            if isinstance(converted_value, Path):
                if (
                    not port_utils.is_file_type(self.property_type)
                    or not converted_value.exists()
                    or converted_value.is_dir()
                ):
                    raise InvalidItemTypeError(self.property_type, f"{new_value}")

                _check_if_symlink_is_valid(converted_value)

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

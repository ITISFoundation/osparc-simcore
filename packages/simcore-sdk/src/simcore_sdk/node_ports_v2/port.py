import logging
import os
from pathlib import Path
from pprint import pformat
from typing import Any, Callable, Dict, Optional, Tuple, Type

from jsonschema import ValidationError
from models_library.services import PROPERTY_KEY_RE, BaseServiceIOModel
from pydantic import AnyUrl, Field, PrivateAttr, validator
from simcore_sdk.node_ports_common.storage_client import LinkType
from pydantic.tools import parse_obj_as

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
from .port_validation import validate_port_content

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


def can_parse_as(v, *types_):
    try:
        for type_ in types_:
            parse_obj_as(v, type_)
    except ValidationError:
        return False


class Port(BaseServiceIOModel):
    key: str = Field(..., regex=PROPERTY_KEY_RE)
    widget: Optional[Dict[str, Any]] = None

    default_value: Optional[DataItemValue] = Field(None, alias="defaultValue")
    value: Optional[DataItemValue] = None

    # TODO: PC unit: Optional[UnitStr] = None

    # Final value types
    _py_value_type: Tuple[Type[ItemConcreteValue], ...] = PrivateAttr()
    # Function to convert to final value types
    _py_value_converter: Callable[[Any], ItemConcreteValue] = PrivateAttr()
    # parent node container this port as input or output
    _node_ports = PrivateAttr()
    # flags
    _used_default_value: bool = PrivateAttr(False)

    _item_value: Optional[ItemValue] = PrivateAttr(None)
    _concrete_value: Optional[ItemConcreteValue] = PrivateAttr(None)

    class Config(BaseServiceIOModel.Config):
        validate_assignment = (
            True  # NOTE: ensures validation of 'value' using setters member functions
        )

    @validator("value", always=True)
    @classmethod
    def check_value(cls, v: DataItemValue, values: Dict[str, Any]) -> DataItemValue:

        if v is not None and (property_type := values.get("property_type")):
            if port_utils.is_file_type(property_type):
                if not isinstance(v, (FileLink, DownloadLink, PortLink)):
                    raise ValueError(
                        f"[{values['property_type']}] must follow "
                        f"{FileLink.schema()}, {DownloadLink.schema()} or {PortLink.schema()}"
                    )
            elif property_type == "ref_contentSchema" and not can_parse_as(v, PortLink):
                v, _ = validate_port_content(
                    port_key=values["key"],
                    value=v,
                    unit=None,
                    content_schema=values["content_schema"],
                )
            else:
                if isinstance(v, (list, dict)):
                    # TODO: SEE https://github.com/ITISFoundation/osparc-simcore/issues/2849
                    raise ValueError(
                        f"Containers as {v} currently only supported within content_schema"
                    )
        return v

    @validator("_item_value", "_concrete_value", pre=True)
    @classmethod
    def check_item_or_concrete_value(cls, v, values):
        if v and (property_type := values.get("property_type")):
            if property_type == "ref_contentSchema" and not can_parse_as(
                v, Path, AnyUrl
            ):
                v, _ = validate_port_content(
                    port_key=values["key"],
                    value=v,
                    unit=None,
                    content_schema=values["content_schema"],
                )

        return v

    def __init__(self, **data: Any):
        super().__init__(**data)

        if port_utils.is_file_type(self.property_type):
            self._py_value_type = (Path, str)
            self._py_value_converter = Path

        elif self.property_type == "ref_contentSchema":
            self._py_value_type = (int, float, bool, str, list, dict)
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

    async def get_value(
        self, *, file_link_type: Optional[LinkType] = None
    ) -> Optional[ItemValue]:
        """Resolves data links and returns resulted value

        Transforms DataItemValue value -> ItemValue
        """
        if not file_link_type:
            file_link_type = LinkType.PRESIGNED

        log.debug(
            "getting value of %s[%s] containing '%s' using %s",
            self.key,
            self.property_type,
            pformat(self.value),
            file_link_type,
        )

        async def _evaluate():
            if isinstance(self.value, PortLink):
                # this is a link to another node's port
                other_port_itemvalue: Optional[
                    ItemValue
                ] = await port_utils.get_value_link_from_port_link(
                    self.value,
                    # pylint: disable=protected-access
                    self._node_ports._node_ports_creator_cb,
                    file_link_type=file_link_type,
                )
                # TODO: PC: add validation/conversion here as well

                return other_port_itemvalue

            if isinstance(self.value, FileLink):
                # let's get the download/upload link from storage
                url_itemvalue: Optional[
                    AnyUrl
                ] = await port_utils.get_download_link_from_storage(
                    # pylint: disable=protected-access
                    user_id=self._node_ports.user_id,
                    value=self.value,
                    link_type=file_link_type,
                )
                return url_itemvalue

            if isinstance(self.value, DownloadLink):
                # generic download link for a file
                return self.value.download_link

            # otherwise, this is a BasicValueTypes
            return self.value

        if not self._item_value:
            self._item_value = await _evaluate()

        return self._item_value

    async def get(self) -> Optional[ItemConcreteValue]:
        """
        Transforms DataItemValue value -> ItemConcreteValue
        """
        log.debug(
            "getting %s[%s] with value %s",
            self.key,
            self.property_type,
            pformat(self.value),
        )

        async def _evaluate():
            if self.value is None:
                return None

            if isinstance(self.value, PortLink):
                # this is a link to another node
                other_port_concretevalue: Optional[
                    ItemConcreteValue
                ] = await port_utils.get_value_from_link(
                    # pylint: disable=protected-access
                    key=self.key,
                    value=self.value,
                    fileToKeyMap=self.file_to_key_map,
                    node_port_creator=self._node_ports._node_ports_creator_cb,
                )
                value = other_port_concretevalue

            elif isinstance(self.value, FileLink):
                # this is a link from storage
                path_concrete_value: Path = await port_utils.pull_file_from_store(
                    user_id=self._node_ports.user_id,
                    key=self.key,
                    fileToKeyMap=self.file_to_key_map,
                    value=self.value,
                )
                value = path_concrete_value

            elif isinstance(self.value, DownloadLink):
                # this is a downloadable link
                path_concrete_value: Path = (
                    await port_utils.pull_file_from_download_link(
                        key=self.key,
                        fileToKeyMap=self.file_to_key_map,
                        value=self.value,
                    )
                )
                value = path_concrete_value

            else:
                # otherwise, this is a BasicValueTypes
                value = self.value

            # don't atempt conversion of None it fails
            if value is None:
                return None

            concrete_value = self._py_value_converter(value)
            return concrete_value

        if not self._concrete_value:
            self._concrete_value = await _evaluate()

        return self._concrete_value

    async def _set(self, new_concrete_value: ItemConcreteValue) -> None:
        log.debug(
            "setting %s[%s] with concrete value %s",
            self.key,
            self.property_type,
            new_concrete_value,
        )
        new_value: Optional[DataItemValue] = None
        if new_concrete_value is not None:
            converted_value = self._py_value_converter(new_concrete_value)
            if isinstance(converted_value, Path):
                if (
                    not port_utils.is_file_type(self.property_type)
                    or not converted_value.exists()
                    or converted_value.is_dir()
                ):
                    raise InvalidItemTypeError(
                        self.property_type, f"{new_concrete_value}"
                    )

                _check_if_symlink_is_valid(converted_value)

                new_value = await port_utils.push_file_to_store(
                    file=converted_value,
                    user_id=self._node_ports.user_id,
                    project_id=self._node_ports.project_id,
                    node_id=self._node_ports.node_uuid,
                )
            else:
                new_value = converted_value

        self.value = new_value
        self._item_value = None
        self._concrete_value = None
        self._used_default_value = False

    async def set(self, new_value: ItemConcreteValue) -> None:
        """sets a value to the port, by default it is also stored in the database"""
        await self._set(new_value)
        await self._node_ports.save_to_db_cb(self._node_ports)

    async def set_value(self, new_item_value: Optional[ItemValue]) -> None:
        """set the value on the port using an item-value"""
        log.debug(
            "setting %s[%s] with value %s", self.key, self.property_type, new_item_value
        )
        if port_utils.is_file_type(self.property_type) and new_item_value is not None:
            if not isinstance(new_item_value, AnyUrl):
                raise InvalidItemTypeError(self.property_type, f"{new_item_value}")

            new_filelink: FileLink = await port_utils.get_file_link_from_url(
                new_item_value,
                self._node_ports.user_id,
                self._node_ports.project_id,
                self._node_ports.node_uuid,
            )

            self.value = new_filelink

        else:
            new_concrete_value: ItemConcreteValue = self._py_value_converter(
                new_item_value
            )
            self._concrete_value = None
            self.value = new_concrete_value  # type:ignore

        self._item_value = None
        self._concrete_value = None
        self._used_default_value = False
        await self._node_ports.save_to_db_cb(self._node_ports)

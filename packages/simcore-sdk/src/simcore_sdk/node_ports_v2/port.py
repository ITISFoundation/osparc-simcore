import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
from typing import Any

from models_library.api_schemas_storage import LinkType
from models_library.basic_types import IDStr
from models_library.services_io import BaseServiceIOModel
from models_library.services_types import ServicePortKey
from pydantic import (
    AnyUrl,
    ConfigDict,
    Field,
    PrivateAttr,
    TypeAdapter,
    ValidationError,
    ValidationInfo,
    field_validator,
)
from servicelib.progress_bar import ProgressBarData

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


TYPE_TO_PYTYPE: dict[str, type[ItemConcreteValue]] = {
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


def can_parse_as(v, *types) -> bool:
    try:
        for type_ in types:
            TypeAdapter(type_).validate_python(v)
        return True
    except ValidationError:
        return False


@dataclass(frozen=True)
class SetKWargs:
    file_base_path: Path | None = None


class Port(BaseServiceIOModel):
    key: ServicePortKey
    widget: dict[str, Any] | None = None
    default_value: DataItemValue | None = Field(
        None, alias="defaultValue", union_mode="left_to_right"
    )

    value: DataItemValue | None = Field(
        None, validate_default=True, union_mode="left_to_right"
    )

    # Different states of "value"
    #   - e.g. typically after resolving a port's link, a download link, ...
    #   - lazy evaluation using get_* members
    #   - used to run validation & conversion of resolved PortContentTypes values
    #   - excluded from all model export
    value_item: ItemValue | None = Field(None, exclude=True, union_mode="left_to_right")
    value_concrete: ItemConcreteValue | None = Field(
        None, exclude=True, union_mode="left_to_right"
    )

    # Function to convert from ItemValue -> ItemConcreteValue
    _py_value_converter: Callable[[Any], ItemConcreteValue] = PrivateAttr()
    # Reference to the `NodePorts` instance that contains this port
    _node_ports = PrivateAttr()

    # flags
    _used_default_value: bool = PrivateAttr(False)

    model_config = ConfigDict(validate_assignment=True)

    @field_validator("value")
    @classmethod
    def check_value(cls, v: DataItemValue, info: ValidationInfo) -> DataItemValue:
        if (
            v is not None
            and (property_type := info.data.get("property_type"))
            and not isinstance(v, PortLink)
        ):
            if port_utils.is_file_type(property_type):
                if not isinstance(v, (FileLink, DownloadLink)):
                    raise ValueError(
                        f"{property_type!r} value does not validate against any of FileLink, DownloadLink or PortLink schemas"
                    )
            elif property_type == "ref_contentSchema":
                v, _ = validate_port_content(
                    port_key=info.data.get("key"),
                    value=v,
                    unit=None,
                    content_schema=info.data.get("content_schema", {}),
                )
            elif isinstance(v, (list, dict)):
                raise TypeError(
                    f"Containers as {v} currently only supported within content_schema."
                )
        return v

    @field_validator("value_item", "value_concrete", mode="before")
    @classmethod
    def check_item_or_concrete_value(cls, v, info: ValidationInfo):
        if (
            v
            and v != info.data["value"]
            and (property_type := info.data.get("property_type"))
            and property_type == "ref_contentSchema"
            and not can_parse_as(v, Path, AnyUrl)
        ):
            v, _ = validate_port_content(
                port_key=info.data.get("key"),
                value=v,
                unit=None,
                content_schema=info.data.get("content_schema", {}),
            )

        return v

    def __init__(self, **data: Any):
        super().__init__(**data)

        if port_utils.is_file_type(self.property_type):
            self._py_value_converter = Path

        elif self.property_type == "ref_contentSchema":

            def _converter(value: ItemConcreteValue) -> ItemConcreteValue:
                return value

            self._py_value_converter = _converter

        else:
            assert self.property_type in TYPE_TO_PYTYPE  # nosec
            self._py_value_converter = TYPE_TO_PYTYPE[self.property_type]

            if self.value is None and self.default_value is not None:
                self.value = self.default_value
                self._used_default_value = True

        assert self._py_value_converter  # nosec

    async def get_value(
        self, *, file_link_type: LinkType | None = None
    ) -> ItemValue | None:
        """Resolves data links and returns resulted value

        Transforms DataItemValue value -> ItemValue

        :raises ValidationError
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

        async def _evaluate() -> ItemValue | None:
            if isinstance(self.value, PortLink):
                # this is a link to another node's port
                other_port_itemvalue: None | (
                    ItemValue
                ) = await port_utils.get_value_link_from_port_link(
                    self.value,
                    # pylint: disable=protected-access
                    self._node_ports._node_ports_creator_cb,
                    file_link_type=file_link_type,
                )

                return other_port_itemvalue

            if isinstance(self.value, FileLink):
                # let's get the download/upload link from storage
                url_itemvalue: None | (
                    AnyUrl
                ) = await port_utils.get_download_link_from_storage(
                    # pylint: disable=protected-access
                    user_id=self._node_ports.user_id,
                    value=self.value,
                    link_type=file_link_type,
                )
                return url_itemvalue

            if isinstance(self.value, DownloadLink):
                # generic download link for a file
                url: AnyUrl = TypeAdapter(AnyUrl).validate_python(
                    self.value.download_link
                )
                return url

            # otherwise, this is a BasicValueTypes
            return self.value

        # assigns to validate result
        v = await _evaluate()
        if v != self.value_item:
            self.value_item = v
        return v

    async def get(
        self, progress_bar: ProgressBarData | None = None
    ) -> ItemConcreteValue | None:
        """
        Transforms DataItemValue value -> ItemConcreteValue

        :raises ValidationError
        """
        log.debug(
            "getting %s[%s] with value %s",
            self.key,
            self.property_type,
            pformat(self.value),
        )

        async def _evaluate() -> ItemConcreteValue | None:
            if self.value is None:
                return None

            if isinstance(self.value, PortLink):
                # this is a link to another node
                other_port_concretevalue: None | (
                    ItemConcreteValue
                ) = await port_utils.get_value_from_link(
                    # pylint: disable=protected-access
                    key=self.key,
                    value=self.value,
                    file_to_key_map=self.file_to_key_map,
                    node_port_creator=self._node_ports._node_ports_creator_cb,  # noqa: SLF001
                    progress_bar=progress_bar,
                )
                value = other_port_concretevalue

            elif isinstance(self.value, FileLink):
                # this is a link from storage
                value = await port_utils.pull_file_from_store(
                    user_id=self._node_ports.user_id,
                    key=self.key,
                    file_to_key_map=self.file_to_key_map,
                    value=self.value,
                    io_log_redirect_cb=self._node_ports.io_log_redirect_cb,
                    r_clone_settings=self._node_ports.r_clone_settings,
                    progress_bar=progress_bar,
                    aws_s3_cli_settings=self._node_ports.aws_s3_cli_settings,
                )

            elif isinstance(self.value, DownloadLink):
                # this is a downloadable link
                value = await port_utils.pull_file_from_download_link(
                    key=self.key,
                    file_to_key_map=self.file_to_key_map,
                    value=self.value,
                    io_log_redirect_cb=self._node_ports.io_log_redirect_cb,
                    progress_bar=progress_bar,
                )

            else:
                # otherwise, this is a BasicValueTypes
                value = self.value

            # don't atempt conversion of None it fails
            if value is None:
                return None

            concrete_value = self._py_value_converter(value)
            return concrete_value

        # assigns to validate result
        v = await _evaluate()
        if v != self.value_concrete:
            self.value_concrete = v
        return v

    async def _set(
        self,
        new_concrete_value: ItemConcreteValue | None,
        *,
        set_kwargs: SetKWargs | None = None,
        progress_bar: ProgressBarData,
    ) -> None:
        """
        :raises InvalidItemTypeError
        :raises ValidationError
        """
        log.debug(
            "setting %s[%s] with concrete value %s",
            self.key,
            self.property_type,
            new_concrete_value,
        )
        new_value: DataItemValue | None = None
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

                # NOTE: the file will be saved in S3 as PROJECT_ID/NODE_ID/(set_kwargs.file_base_path)/PORT_KEY/file.ext
                base_path = Path(self.key)
                if set_kwargs and set_kwargs.file_base_path:
                    base_path = set_kwargs.file_base_path / self.key

                new_value = await port_utils.push_file_to_store(
                    file=converted_value,
                    user_id=self._node_ports.user_id,
                    project_id=self._node_ports.project_id,
                    node_id=self._node_ports.node_uuid,
                    r_clone_settings=self._node_ports.r_clone_settings,
                    io_log_redirect_cb=self._node_ports.io_log_redirect_cb,
                    file_base_path=base_path,
                    progress_bar=progress_bar,
                    aws_s3_cli_settings=self._node_ports.aws_s3_cli_settings,
                )
            else:
                new_value = converted_value
                await progress_bar.update()
        else:
            await progress_bar.update()

        self.value = new_value
        self.value_item = None
        self.value_concrete = None
        self._used_default_value = False

    async def set(
        self,
        new_value: ItemConcreteValue,
        *,
        progress_bar: ProgressBarData | None = None,
        **set_kwargs,
    ) -> None:
        """sets a value to the port, by default it is also stored in the database

        :raises InvalidItemTypeError
        :raises ValidationError
        """
        await self._set(
            new_concrete_value=new_value,
            **set_kwargs,
            progress_bar=progress_bar
            or ProgressBarData(num_steps=1, description=IDStr("set")),
        )
        await self._node_ports.save_to_db_cb(self._node_ports)

    async def set_value(self, new_item_value: ItemValue | None) -> None:
        """set the value on the port using an item-value

        :raises InvalidItemTypeError
        :raises ValidationError
        """
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
            self.value_concrete = None
            self.value = new_concrete_value  # type: ignore[assignment]

        self.value_item = None
        self.value_concrete = None
        self._used_default_value = False
        await self._node_ports.save_to_db_cb(self._node_ports)

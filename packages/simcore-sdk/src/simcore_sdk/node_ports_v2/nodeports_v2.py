import logging
import traceback
from abc import ABC, abstractmethod
from asyncio import CancelledError, Task
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import Any

from models_library.api_schemas_storage import LinkType
from models_library.basic_types import IDStr
from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from models_library.services_types import ServicePortKey
from models_library.users import UserID
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from pydantic_core import InitErrorDetails
from servicelib.progress_bar import ProgressBarData
from servicelib.utils import logged_gather
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.r_clone import RCloneSettings

from ..node_ports_common.dbmanager import DBManager
from ..node_ports_common.exceptions import PortNotFound, UnboundPortError
from ..node_ports_common.file_io_utils import LogRedirectCB
from ..node_ports_v2.port import SetKWargs
from .links import ItemConcreteValue, ItemValue
from .port_utils import is_file_type
from .ports_mapping import InputsList, OutputsList

log = logging.getLogger(__name__)


#  -> @GitHK this looks very dangerous, using a lot of protected stuff, just checking the number of ignores shows it's a bad idea...
def _format_error(task: Task) -> str:
    # pylint:disable=protected-access
    assert task._exception  # nosec  # noqa: SLF001
    error_list = traceback.format_exception(
        type(task._exception),  # noqa: SLF001
        task._exception,  # noqa: SLF001
        task._exception.__traceback__,  # noqa: SLF001
    )
    return "\n".join(error_list)


def _get_error_details(task: Task, port_key: str) -> InitErrorDetails:
    # pylint:disable=protected-access
    return InitErrorDetails(
        type="value_error",
        loc=(f"{port_key}",),
        input=_format_error(task),
        ctx={"error": task._exception},  # noqa: SLF001
    )


class OutputsCallbacks(ABC):
    @abstractmethod
    async def aborted(self, key: ServicePortKey) -> None:
        pass

    @abstractmethod
    async def finished_succesfully(self, key: ServicePortKey) -> None:
        pass

    @abstractmethod
    async def finished_with_error(self, key: ServicePortKey) -> None:
        pass


class Nodeports(BaseModel):
    """
    Represents a node in a project and all its input/output ports
    """

    internal_inputs: InputsList = Field(..., alias="inputs")
    internal_outputs: OutputsList = Field(..., alias="outputs")
    db_manager: DBManager
    user_id: UserID
    project_id: ProjectIDStr
    node_uuid: NodeIDStr
    save_to_db_cb: Callable[["Nodeports"], Coroutine[Any, Any, None]]
    node_port_creator_cb: Callable[
        [DBManager, UserID, ProjectIDStr, NodeIDStr],
        Coroutine[Any, Any, type["Nodeports"]],
    ]
    auto_update: bool = False
    r_clone_settings: RCloneSettings | None = None
    io_log_redirect_cb: LogRedirectCB | None
    aws_s3_cli_settings: AwsS3CliSettings | None = None
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    def __init__(self, **data: Any):
        super().__init__(**data)
        # pylint: disable=protected-access

        # let's pass ourselves down
        for input_key in self.internal_inputs:
            self.internal_inputs[input_key]._node_ports = self  # noqa: SLF001
        for output_key in self.internal_outputs:
            self.internal_outputs[output_key]._node_ports = self  # noqa: SLF001

    @property
    async def inputs(self) -> InputsList:
        log.debug("Getting inputs with autoupdate: %s", self.auto_update)
        if self.auto_update:
            await self._auto_update_from_db()
        return self.internal_inputs

    @property
    async def outputs(self) -> OutputsList:
        log.debug("Getting outputs with autoupdate: %s", self.auto_update)
        if self.auto_update:
            await self._auto_update_from_db()
        return self.internal_outputs

    async def get_value_link(
        self, item_key: ServicePortKey, *, file_link_type: LinkType
    ) -> ItemValue | None:
        try:
            return await (await self.inputs)[item_key].get_value(
                file_link_type=file_link_type
            )
        except UnboundPortError:
            # not available try outputs
            pass
        # if this fails it will raise an exception
        return await (await self.outputs)[item_key].get_value(
            file_link_type=file_link_type
        )

    async def get(
        self, item_key: ServicePortKey, progress_bar: ProgressBarData | None = None
    ) -> ItemConcreteValue | None:
        try:
            return await (await self.inputs)[item_key].get(progress_bar)
        except UnboundPortError:
            # not available try outputs
            pass
        # if this fails it will raise an exception
        return await (await self.outputs)[item_key].get(progress_bar)

    async def set(
        self, item_key: ServicePortKey, item_value: ItemConcreteValue
    ) -> None:
        # first try to set the inputs.
        try:
            the_updated_inputs = await self.inputs
            await the_updated_inputs[item_key].set(item_value)
            return
        except UnboundPortError:
            # not available try outputs
            # if this fails it will raise another exception
            the_updated_outputs = await self.outputs
            await the_updated_outputs[item_key].set(item_value)

    async def set_file_by_keymap(self, item_value: Path) -> None:
        for output in (await self.outputs).values():
            if (is_file_type(output.property_type) and output.file_to_key_map) and (
                item_value.name in output.file_to_key_map
            ):
                await output.set(item_value)
                return
        raise PortNotFound(msg=f"output port for item {item_value} not found")

    async def _node_ports_creator_cb(self, node_uuid: NodeIDStr) -> type["Nodeports"]:
        return await self.node_port_creator_cb(
            self.db_manager, self.user_id, self.project_id, node_uuid
        )

    async def _auto_update_from_db(self) -> None:
        # get the newest from the DB
        updated_node_ports = await self._node_ports_creator_cb(self.node_uuid)
        # update our stuff
        self.internal_inputs = updated_node_ports.internal_inputs
        self.internal_outputs = updated_node_ports.internal_outputs
        # let's pass ourselves down
        # pylint: disable=protected-access
        for input_key in self.internal_inputs:
            self.internal_inputs[input_key]._node_ports = self  # noqa: SLF001
        for output_key in self.internal_outputs:
            self.internal_outputs[output_key]._node_ports = self  # noqa: SLF001

    async def set_multiple(
        self,
        port_values: dict[
            ServicePortKey, tuple[ItemConcreteValue | None, SetKWargs | None]
        ],
        *,
        progress_bar: ProgressBarData,
        outputs_callbacks: OutputsCallbacks | None,
    ) -> None:
        """
        Sets the provided values to the respective input or output ports
        Only supports port_key by name, not able to distinguish between inputs
        and outputs using the index.

        raises ValidationError
        """

        async def _set_with_notifications(
            port_key: ServicePortKey,
            value: ItemConcreteValue | None,
            set_kwargs: SetKWargs | None,
            sub_progress: ProgressBarData,
        ) -> None:
            try:
                # pylint: disable=protected-access
                await self.internal_outputs[port_key]._set(  # noqa: SLF001
                    value, set_kwargs=set_kwargs, progress_bar=sub_progress
                )
                if outputs_callbacks:
                    await outputs_callbacks.finished_succesfully(port_key)
            except UnboundPortError:
                # not available try inputs
                # if this fails it will raise another exception
                # pylint: disable=protected-access
                await self.internal_inputs[port_key]._set(  # noqa: SLF001
                    value, set_kwargs=set_kwargs, progress_bar=sub_progress
                )
            except CancelledError:
                if outputs_callbacks:
                    await outputs_callbacks.aborted(port_key)
                raise
            except Exception:
                if outputs_callbacks:
                    await outputs_callbacks.finished_with_error(port_key)
                raise

        tasks = []
        async with progress_bar.sub_progress(
            steps=len(port_values.items()), description=IDStr("set multiple")
        ) as sub_progress:
            for port_key, (value, set_kwargs) in port_values.items():
                tasks.append(
                    _set_with_notifications(port_key, value, set_kwargs, sub_progress)
                )

            results = await logged_gather(*tasks)
            await self.save_to_db_cb(self)

        # groups all ValidationErrors pre-pending 'port_key' to loc and raises ValidationError
        if error_details := [
            _get_error_details(r, port_key)
            for port_key, r in zip(port_values.keys(), results, strict=False)
            if r is not None
        ]:
            raise ValidationError.from_exception_data(
                title="Multiple port_key errors", line_errors=error_details
            )

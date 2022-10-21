import logging
from collections import deque
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from models_library.users import UserID
from pydantic import BaseModel, Field, ValidationError
from pydantic.error_wrappers import flatten_errors
from servicelib.utils import logged_gather
from settings_library.r_clone import RCloneSettings

from ..node_ports_common.dbmanager import DBManager
from ..node_ports_common.exceptions import PortNotFound, UnboundPortError
from ..node_ports_common.file_io_utils import LogRedirectCB
from ..node_ports_common.storage_client import LinkType
from ..node_ports_v2.port import SetKWargs
from .links import ItemConcreteValue, ItemValue
from .port_utils import is_file_type
from .ports_mapping import InputsList, OutputsList

log = logging.getLogger(__name__)


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
    r_clone_settings: Optional[RCloneSettings] = None
    io_log_redirect_cb: Optional[LogRedirectCB]

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data: Any):
        super().__init__(**data)
        # pylint: disable=protected-access

        # let's pass ourselves down
        for input_key in self.internal_inputs:
            self.internal_inputs[input_key]._node_ports = self
        for output_key in self.internal_outputs:
            self.internal_outputs[output_key]._node_ports = self

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
        self, item_key: str, *, file_link_type: LinkType
    ) -> Optional[ItemValue]:
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

    async def get(self, item_key: str) -> Optional[ItemConcreteValue]:
        try:
            return await (await self.inputs)[item_key].get()
        except UnboundPortError:
            # not available try outputs
            pass
        # if this fails it will raise an exception
        return await (await self.outputs)[item_key].get()

    async def set(self, item_key: str, item_value: ItemConcreteValue) -> None:
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
            if is_file_type(output.property_type) and output.file_to_key_map:
                if item_value.name in output.file_to_key_map:
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
            self.internal_inputs[input_key]._node_ports = self
        for output_key in self.internal_outputs:
            self.internal_outputs[output_key]._node_ports = self

    async def set_multiple(
        self,
        port_values: dict[str, tuple[Optional[ItemConcreteValue], Optional[SetKWargs]]],
    ) -> None:
        """
        Sets the provided values to the respective input or output ports
        Only supports port_key by name, not able to distinguish between inputs
        and outputs using the index.

        raises ValidationError
        """
        tasks = deque()
        for port_key, (value, set_kwargs) in port_values.items():
            # pylint: disable=protected-access
            try:
                tasks.append(self.internal_outputs[port_key]._set(value, set_kwargs))
            except UnboundPortError:
                # not available try inputs
                # if this fails it will raise another exception
                tasks.append(self.internal_inputs[port_key]._set(value, set_kwargs))

        results = await logged_gather(*tasks)
        await self.save_to_db_cb(self)

        # groups all ValidationErrors pre-pending 'port_key' to loc and raises ValidationError
        if errors := [
            flatten_errors(r, self.__config__, loc=(f"{port_key}",))
            for port_key, r in zip(port_values.keys(), results)
            if isinstance(r, ValidationError)
        ]:
            raise ValidationError(errors, model=self)

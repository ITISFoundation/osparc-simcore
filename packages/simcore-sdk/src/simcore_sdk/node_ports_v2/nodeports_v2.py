import logging
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional, Type

from pydantic import BaseModel, Field

from ..node_ports_common.dbmanager import DBManager
from ..node_ports_common.exceptions import PortNotFound, UnboundPortError
from .links import ItemConcreteLinkValue, ItemConcreteValue
from .port_utils import is_file_type
from .ports_mapping import InputsList, OutputsList

log = logging.getLogger(__name__)


class Nodeports(BaseModel):
    internal_inputs: InputsList = Field(..., alias="inputs")
    internal_outputs: OutputsList = Field(..., alias="outputs")
    db_manager: DBManager
    user_id: int
    project_id: str
    node_uuid: str
    save_to_db_cb: Callable[["Nodeports"], Coroutine[Any, Any, None]]
    node_port_creator_cb: Callable[
        [DBManager, int, str, str], Coroutine[Any, Any, Type["Nodeports"]]
    ]
    auto_update: bool = False

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
        self, item_key: str, download: bool
    ) -> Optional[ItemConcreteLinkValue]:
        try:
            return await (await self.inputs)[item_key].get_value_link(download=download)
        except UnboundPortError:
            # not available try outputs
            pass
        # if this fails it will raise an exception
        return await (await self.outputs)[item_key].get_value_link(download=download)

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

    async def _node_ports_creator_cb(self, node_uuid: str) -> Type["Nodeports"]:
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

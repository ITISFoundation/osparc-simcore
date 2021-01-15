import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine, Type

from models_library.projects_nodes_io import PortLink
from pydantic import BaseModel, Field

from ..node_ports.dbmanager import DBManager
from ..node_ports.exceptions import PortNotFound, UnboundPortError
from .links import ItemConcreteValue
from .port_utils import is_file_type
from .ports_mapping import InputsList, OutputsList

log = logging.getLogger(__name__)


class Nodeports(BaseModel):
    internal_inputs: InputsList = Field(..., alias="inputs")
    internal_outputs: OutputsList = Field(..., alias="outputs")
    db_manager: DBManager
    node_uuid: str
    save_to_db_cb: Callable[["Nodeports"], Coroutine[Any, Any, None]]
    node_port_creator_cb: Callable[[DBManager, str], Coroutine[Any, Any, "Nodeports"]]
    auto_update: bool = False

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, **data: Any):
        super().__init__(**data)
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

    @property
    async def run_hash(self) -> str:
        import pdb

        pdb.set_trace()
        # resolve the port links if any
        io_payload = {"inputs": {}, "outputs": {}}
        for port_key, port_value in (await self.inputs).items():
            if isinstance(port_value.value, PortLink):
                # resolve the entry
                other_nodeports = await self._node_ports_creator_cb(
                    port_value.value.node_uuid
                )
                io_payload["inputs"][port_key] = (await other_nodeports.outputs)[
                    port_value.value.output
                ].value
            else:
                io_payload["inputs"][port_key] = port_value.value
        for port_key, port_value in (await self.outputs).items():
            io_payload["outputs"][port_key] = port_value.value

        # for input_key, input_value in (await self.inputs).items():
        #     if isinstance(input_value, PortLink):
        #         # let's resolve the entry
        #         previous_node = nodes_data_view[str(input_value.node_uuid)]
        #         previous_node_outputs = previous_node.get("outputs", {})
        #         resolved_inputs[input_key] = previous_node_outputs.get(
        #             input_value.output
        #         )
        #     else:
        #         resolved_inputs[input_key] = input_value

        block_string = json.dumps(io_payload).encode("utf-8")
        raw_hash = hashlib.sha256(block_string)
        return raw_hash.hexdigest()

        # class PydanticEncoder(json.JSONEncoder):
        #     def default(self, o):
        #         if isinstance(o, BaseModel):
        #             return o.json()
        #         return json.JSONEncoder.default(self, o)

        # block_string = json.dumps(io_payload, cls=PydanticEncoder).encode("utf-8")
        # raw_hash = hashlib.sha256(block_string)
        # return raw_hash.hexdigest()

    async def get(self, item_key: str) -> ItemConcreteValue:
        try:
            return await (await self.inputs)[item_key].get()
        except UnboundPortError:
            # not available try outputs
            pass
        # if this fails it will raise an exception
        return await (await self.outputs)[item_key].get()

    async def set(self, item_key: str, item_value: ItemConcreteValue) -> None:
        try:
            await (await self.inputs)[item_key].set(item_value)
            return
        except UnboundPortError:
            # not available try outputs
            pass
        # if this fails it will raise an exception
        await (await self.outputs)[item_key].set(item_value)

    async def set_file_by_keymap(self, item_value: Path) -> None:
        for output in (await self.outputs).values():
            if is_file_type(output.property_type) and output.file_to_key_map:
                if item_value.name in output.file_to_key_map:
                    await output.set(item_value)
                    return
        raise PortNotFound(msg=f"output port for item {item_value} not found")

    async def _node_ports_creator_cb(self, node_uuid: str) -> Type["Nodeports"]:
        return await self.node_port_creator_cb(self.db_manager, node_uuid)

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

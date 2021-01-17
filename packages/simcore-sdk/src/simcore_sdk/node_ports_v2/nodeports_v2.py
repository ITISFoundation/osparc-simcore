import hashlib
import json
import logging
from pathlib import Path
from pprint import pformat
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
        log.debug("Getting run_hash")
        # resolve the port links if any and get only the payload
        io_payload = {}
        for port_type in ["inputs", "outputs"]:
            io_payload[port_type] = {}
            for port_key, port in (getattr(self, f"internal_{port_type}")).items():
                payload = port.value
                if isinstance(port.value, PortLink):
                    # in case of a port link we do resolve the entry so we have the real value for the hashing
                    linked_nodeports = await self._node_ports_creator_cb(
                        port.value.node_uuid
                    )
                    payload = (await linked_nodeports.outputs)[port.value.output].value

                # ensure we do not get pydantic types for hashing here
                if isinstance(payload, BaseModel):
                    payload = payload.dict(by_alias=True, exclude_unset=True)
                if payload is not None:
                    io_payload[port_type][port_key] = payload

        log.debug("io_payload generated is %s", pformat(io_payload))
        block_string = json.dumps(io_payload).encode("utf-8")
        log.debug("block string generated is %s", block_string)
        raw_hash = hashlib.sha256(block_string)
        log.debug("generated hash %s", raw_hash)
        return raw_hash.hexdigest()

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

import logging
from typing import Optional

from ..node_ports import config as node_config
from ..node_ports import exceptions
from ..node_ports.dbmanager import DBManager
from .nodeports_v2 import Nodeports
from .port import Port
from .serialization_v2 import load

log = logging.getLogger(__name__)


async def ports(db_manager: Optional[DBManager] = None) -> Nodeports:
    log.debug("creating node_ports_v2 object using provided dbmanager: %s", db_manager)
    # FIXME: warning every dbmanager create a new db engine!
    if db_manager is None:  # NOTE: keeps backwards compatibility
        log.debug("no db manager provided, creating one...")
        db_manager = DBManager()

    return await load(db_manager, node_config.NODE_UUID, auto_update=True)


__all__ = ["ports", "node_config", "exceptions", "Port"]

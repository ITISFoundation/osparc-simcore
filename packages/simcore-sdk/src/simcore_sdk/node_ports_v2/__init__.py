import logging
from typing import Optional

from settings_library.r_clone import RCloneSettings

from ..node_ports_common import exceptions
from ..node_ports_common.dbmanager import DBManager
from ..node_ports_common.storage_client import LinkType as FileLinkType
from .nodeports_v2 import Nodeports
from .port import Port
from .serialization_v2 import load

log = logging.getLogger(__name__)


async def ports(
    user_id: int,
    project_id: str,
    node_uuid: str,
    *,
    db_manager: Optional[DBManager] = None,
    r_clone_settings: Optional[RCloneSettings] = None
) -> Nodeports:
    log.debug("creating node_ports_v2 object using provided dbmanager: %s", db_manager)
    # FIXME: warning every dbmanager create a new db engine!
    if db_manager is None:  # NOTE: keeps backwards compatibility
        log.debug("no db manager provided, creating one...")
        db_manager = DBManager()

    return await load(
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        auto_update=True,
        r_clone_settings=r_clone_settings,
    )


__all__ = ("ports", "exceptions", "Port", "FileLinkType")

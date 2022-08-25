import logging
from typing import Optional

from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from models_library.users import UserID
from settings_library.r_clone import RCloneSettings

from ..node_ports_common import exceptions
from ..node_ports_common.dbmanager import DBManager
from ..node_ports_common.file_io_utils import LogRedirectCB
from ..node_ports_common.storage_client import LinkType as FileLinkType
from .nodeports_v2 import Nodeports
from .port import Port
from .serialization_v2 import load

log = logging.getLogger(__name__)


async def ports(
    user_id: UserID,
    project_id: ProjectIDStr,
    node_uuid: NodeIDStr,
    *,
    db_manager: Optional[DBManager] = None,
    r_clone_settings: Optional[RCloneSettings] = None,
    io_log_redirect_cb: Optional[LogRedirectCB] = None
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
        io_log_redirect_cb=io_log_redirect_cb,
    )


__all__ = ("ports", "exceptions", "Port", "FileLinkType")

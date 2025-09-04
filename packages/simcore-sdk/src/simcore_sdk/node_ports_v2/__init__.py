import logging

from models_library.api_schemas_storage.storage_schemas import LinkType as FileLinkType
from models_library.projects import ProjectIDStr
from models_library.projects_nodes_io import NodeIDStr
from models_library.users import UserID
from settings_library.aws_s3_cli import AwsS3CliSettings
from settings_library.r_clone import RCloneSettings

from ..node_ports_common import exceptions
from ..node_ports_common.dbmanager import DBManager
from ..node_ports_common.file_io_utils import LogRedirectCB
from .nodeports_v2 import Nodeports
from .port import Port
from .serialization_v2 import load

log = logging.getLogger(__name__)


async def ports(
    user_id: UserID,
    project_id: ProjectIDStr,
    node_uuid: NodeIDStr,
    *,
    db_manager: DBManager,
    r_clone_settings: RCloneSettings | None = None,
    io_log_redirect_cb: LogRedirectCB | None = None,
    aws_s3_cli_settings: AwsS3CliSettings | None = None
) -> Nodeports:
    return await load(
        db_manager=db_manager,
        user_id=user_id,
        project_id=project_id,
        node_uuid=node_uuid,
        auto_update=True,
        r_clone_settings=r_clone_settings,
        io_log_redirect_cb=io_log_redirect_cb,
        aws_s3_cli_settings=aws_s3_cli_settings,
    )


__all__ = (
    "DBManager",
    "FileLinkType",
    "Nodeports",
    "Port",
    "exceptions",
    "ports",
)

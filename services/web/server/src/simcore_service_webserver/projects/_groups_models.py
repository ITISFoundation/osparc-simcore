import logging
from datetime import datetime

from models_library.groups import GroupID
from pydantic import BaseModel, ConfigDict

_logger = logging.getLogger(__name__)


class ProjectGroupGetDB(BaseModel):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime

    model_config = ConfigDict(from_attributes=True)

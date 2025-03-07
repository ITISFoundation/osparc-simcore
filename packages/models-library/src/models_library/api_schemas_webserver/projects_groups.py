from datetime import datetime

from models_library.groups import GroupID

from ._base import OutputSchema


class ProjectGroupGet(OutputSchema):
    gid: GroupID
    read: bool
    write: bool
    delete: bool
    created: datetime
    modified: datetime

from umongo import Document, fields

from scheduler.dbs.mongo_models import instance
from scheduler.dbs.mongo_models.utils import BinaryField


@instance.register
class WorkbenchInput(Document):
    """Used to store the incoming workbench configurations"""

    content = fields.DictField(required=True)
    prev_vers_diff = fields.ReferenceField(
        "WorkbenchInputDiff", required=True, default=None
    )


@instance.register
class WorkbenchInputDiff(Document):
    """Stores the diff from previous version"""

    entry = BinaryField(required=True)
    previous_diff = fields.ReferenceField(
        "WorkbenchInputDiff", required=True, default=None
    )

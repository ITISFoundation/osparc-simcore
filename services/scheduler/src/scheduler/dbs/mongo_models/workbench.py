import datetime
from typing import Any, Dict
from uuid import UUID

from deepdiff import DeepDiff, Delta
from umongo import Document, fields, validate

from scheduler.dbs.mongo_models import instance
from scheduler.dbs.mongo_models.utils import BinaryField


@instance.register
class WorkbenchUpdate(Document):
    STATE_EDITABLE = "editable"
    STATE_RUNNING = "running"
    """Used to store the incoming workbench configurations"""

    project_id = fields.UUIDField(required=True, unique=True)

    workbench_state = fields.StringField(
        required=True, validate=validate.OneOf((STATE_RUNNING, STATE_EDITABLE))
    )

    # content of the last workbench
    ui_workbench = fields.DictField(required=True)
    scheduling_workbench = fields.DictField(required=True)

    # last diff used for scheduling, with some fields stripped away
    prev_scheduling_workbench_diff = fields.ReferenceField("WorkbenchDiff")
    # used to keep ui in sync between versions
    prev_ui_workbench_diff = fields.ReferenceField("WorkbenchDiff")

    @classmethod
    async def entry_for_project_id(cls, project_id: str) -> "WorkbenchUpdate":
        return await cls.find_one({"project_id": UUID(project_id)})

    @classmethod
    async def create(cls, project_id: str) -> "WorkbenchUpdate":
        workbench_update = cls(
            project_id=project_id,
            workbench_state=cls.STATE_EDITABLE,
            ui_workbench={},
            scheduling_workbench={},
        )
        await workbench_update.commit()
        return workbench_update

    def requires_pipeline_update(
        self, new_scheduling_workbench: Dict[str, Any]
    ) -> bool:
        """returns: True if somethings needs to be rescheduled"""
        deep_diff = DeepDiff(new_scheduling_workbench, dict(self.scheduling_workbench))
        return deep_diff != {}

    async def insert_diff_if_required(
        self, new_ui_workbench: Dict[str, Any], new_scheduling_workbench: Dict[str, Any]
    ) -> None:
        scheduling_deep_diff = DeepDiff(
            new_scheduling_workbench, dict(self.scheduling_workbench)
        )
        ui_deep_diff = DeepDiff(new_ui_workbench, dict(self.ui_workbench))

        self.scheduling_workbench = new_scheduling_workbench
        self.ui_workbench = new_ui_workbench

        if scheduling_deep_diff == {} and ui_deep_diff == {}:
            return  # do nothing

        # insert a new diff in the database
        current_date = datetime.datetime.utcnow()

        scheduling_workbench_diff_params = dict(
            diff=Delta(scheduling_deep_diff).dumps(), datetime=current_date
        )
        if self.prev_scheduling_workbench_diff is not None:
            scheduling_workbench_diff_params[
                "prev_workbench_diff"
            ] = self.prev_scheduling_workbench_diff
        scheduling_diff = WorkbenchDiff(**scheduling_workbench_diff_params)

        ui_workbench_diff_param = dict(
            diff=Delta(ui_deep_diff).dumps(), datetime=current_date,
        )
        if self.prev_ui_workbench_diff is not None:
            ui_workbench_diff_param["prev_workbench_diff"] = self.prev_ui_workbench_diff
        ui_diff = WorkbenchDiff(**ui_workbench_diff_param)

        await scheduling_diff.commit()
        await ui_diff.commit()
        self.prev_scheduling_workbench_diff = scheduling_diff
        self.prev_ui_workbench_diff = ui_diff
        await self.commit()


@instance.register
class WorkbenchDiff(Document):
    """Stores the diff from previous version"""

    diff = BinaryField(required=True)
    prev_workbench_diff = fields.ReferenceField("WorkbenchDiff")
    datetime = fields.DateTimeField(required=True)

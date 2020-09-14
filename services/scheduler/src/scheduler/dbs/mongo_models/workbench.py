import datetime
from typing import Any, Dict

from deepdiff import DeepDiff, Delta
from umongo import Document, fields, validate

from scheduler.dbs.mongo_models import instance
from scheduler.dbs.mongo_models.utils import BinaryField


@instance.register
class WorkbenchUpdate(Document):
    """Used to store the incoming workbench configurations"""

    # [EDITABLE] Opened in a Browser tab or active in API (actively interacted),
    # the user has just opened the workbench and a RUN command might be issued, or
    # a dynamic service might be opened to view results.
    STATE_EDITABLE = "editable"
    # [RUNNING] Computational pipeline is running, no changes are accepted, and
    # the computational graph will be computed and scheduled for running with
    # updates on all services (creation of containers and starting of containers,
    # based on constraints)
    STATE_RUNNING = "running"
    # [ERROR] Something is not working properly in the pipeline, there might be
    # some issues with the configuration or a runtime error in the acceptance
    # pipeline. the user should be prompted to fix it
    STATE_ERROR = "error"
    # [CLOSED] Closed in a Browser on not active in API (no interactions), the
    # most common state, the project is totally closed (nothing needs to run)
    STATE_CLOSED = "closed"

    project_id = fields.UUIDField(required=True, unique=True)

    workbench_state = fields.StringField(
        required=True,
        validate=validate.OneOf(
            {STATE_RUNNING, STATE_EDITABLE, STATE_ERROR, STATE_CLOSED}
        ),
    )

    # True if opened by the user or used in the API
    is_active = fields.BooleanField(required=True, default=False)

    # content of the last workbench
    ui_workbench = fields.DictField(required=True)
    scheduling_workbench = fields.DictField(required=True)

    # last diff used for scheduling, with some fields stripped away
    prev_scheduling_workbench_diff = fields.ReferenceField("WorkbenchDiff")
    # used to keep ui in sync between versions
    prev_ui_workbench_diff = fields.ReferenceField("WorkbenchDiff")

    @classmethod
    async def entry_for_project_id(cls, project_id: str) -> "WorkbenchUpdate":
        return await cls.find_one({"project_id": project_id})

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

    async def set_active(self, is_active: bool) -> None:
        self.is_active = is_active
        await self.commit()


@instance.register
class WorkbenchDiff(Document):
    """Stores the diff from previous version"""

    diff = BinaryField(required=True)
    prev_workbench_diff = fields.ReferenceField("WorkbenchDiff")
    datetime = fields.DateTimeField(required=True)

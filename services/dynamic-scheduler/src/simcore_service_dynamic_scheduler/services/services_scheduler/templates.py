from .models import DagTemplate

APPLY_WORKFLOW_ID = "dynamic_services_apply_v1"
TEARDOWN_WORKFLOW_ID = "dynamic_services_teardown_v1"


def get_apply_template() -> DagTemplate:
    return DagTemplate(workflow_id=APPLY_WORKFLOW_ID, nodes=set(), edges=set())


def get_teardown_template() -> DagTemplate:
    return DagTemplate(workflow_id=TEARDOWN_WORKFLOW_ID, nodes=set(), edges=set())

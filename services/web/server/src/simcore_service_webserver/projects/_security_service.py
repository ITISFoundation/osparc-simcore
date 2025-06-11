import jsondiff  # type: ignore[import-untyped]
from aiohttp import web
from simcore_postgres_database.models.users import UserRole

from ..security import security_web
from ._projects_repository_legacy import ProjectDBAPI
from .api import check_user_project_permission


async def _can_update_node_inputs(context):
    """Check function associated to "project.workbench.node.inputs.update" permission label

    Returns True if user has permission to update inputs
    """
    db: ProjectDBAPI = context["dbapi"]
    app: web.Application = context["app"]
    project_uuid = context["project_id"]
    user_id = context["user_id"]
    updated_project = context["new_data"]

    if project_uuid is None or user_id is None:
        return False

    product_name = await db.get_project_product(project_uuid)
    await check_user_project_permission(
        app,
        project_id=project_uuid,
        user_id=user_id,
        product_name=product_name,
        permission="read",
    )
    # get current version
    current_project, _ = await db.get_project_dict_and_type(project_uuid)

    diffs = jsondiff.diff(current_project, updated_project)

    if "workbench" in diffs:
        try:
            for node in diffs["workbench"]:
                # can ONLY modify `inputs` fields set as ReadAndWrite
                access = current_project["workbench"][node]["inputAccess"]
                inputs = diffs["workbench"][node]["inputs"]
                return all(access.get(key) == "ReadAndWrite" for key in inputs)
        except KeyError:
            pass
        return False

    return len(diffs) == 0  # no changes


def setup_projects_access(app: web.Application):
    """
    security - access : Inject permissions to rest API resources
    """
    hrba = security_web.get_access_model(app)

    hrba.roles[UserRole.GUEST].check[
        "project.workbench.node.inputs.update"
    ] = _can_update_node_inputs

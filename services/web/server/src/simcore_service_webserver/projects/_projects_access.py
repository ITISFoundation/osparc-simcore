import jsondiff  # type: ignore[import-untyped]
from aiohttp import web
from simcore_postgres_database.models.users import UserRole

from ..security.api import get_access_model
from .db import ProjectDBAPI


async def can_update_node_inputs(context):
    """Check function associated to "project.workbench.node.inputs.update" permission label

    Returns True if user has permission to update inputs
    """
    db: ProjectDBAPI = context["dbapi"]
    project_uuid = context["project_id"]
    user_id = context["user_id"]
    updated_project = context["new_data"]

    if project_uuid is None or user_id is None:
        return False

    # NOTE: MD this needs to be uncommented when I found out how to get access to application (PC help needed)!
    # product_name = await db.get_project_product(project_uuid)
    # prj_access_rights = await get_user_project_access_rights(
    #     app, project_id=project_uuid, user_id=user_id, product_name=product_name
    # )
    # if prj_access_rights.read is False:
    #     raise ProjectInvalidRightsError(user_id=user_id, project_uuid=project_uuid)

    # get current version
    current_project, _ = await db.get_project(project_uuid)

    diffs = jsondiff.diff(current_project, updated_project)

    # TODO: depends on schema. Shall change if schema changes!?
    if "workbench" in diffs:
        try:
            for node in diffs["workbench"]:
                # can ONLY modify `inputs` fields set as ReadAndWrite
                access = current_project["workbench"][node]["inputAccess"]
                inputs = diffs["workbench"][node]["inputs"]
                for key in inputs:
                    if access.get(key) != "ReadAndWrite":
                        return False
                return True
        except KeyError:
            pass
        return False

    return len(diffs) == 0  # no changes


def setup_projects_access(app: web.Application):
    """
    security - access : Inject permissions to rest API resources
    """
    hrba = get_access_model(app)

    # TODO: add here also named permissions, i.e. all project.* operations
    hrba.roles[UserRole.GUEST].check[
        "project.workbench.node.inputs.update"
    ] = can_update_node_inputs

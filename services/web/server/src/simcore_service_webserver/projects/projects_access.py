
import jsondiff
from aiohttp import web

from ..security_api import get_access_model, UserRole
from .projects_fakes import Fake
from .projects_models import ProjectDB


async def can_update_node_inputs(context):
    """ Check function associated to "project.workbench.node.inputs.update" permission label

        Returns True if user has permission to update inputs
    """
    db = context['db_engine']
    project_uuid = context['project_id']
    user_id = context['user_id']
    updated_project = context['new_data']

    if project_uuid is None or user_id is None:
        return False

    # get current version
    # TODO: unify call
    if project_uuid in Fake.projects:
        current_project = Fake.projects[project_uuid].data
    else:
        current_project = await ProjectDB.get_user_project(user_id, project_uuid, db_engine=db)

    diffs = jsondiff.diff(current_project, updated_project)

    # TODO: depends on schema. Shall change if schema changes!?
    if "workbench" in diffs:
        try:
            for node in diffs["workbench"]:
                # can ONLY modify `inputs` fields set as ReadAndWrite
                access = current_project['workbench'][node]["inputAccess"]
                inputs = diffs["workbench"][node]['inputs']
                for key in inputs:
                    if access.get(key) != "ReadAndWrite":
                        return False
                return True
        except KeyError:
            pass
        return False

    return len(diffs)==0 # no changes



def setup_access(app: web.Application):
    """
        security - access : Inject permissions to rest API resources
    """
    hrba = get_access_model(app)

    # TODO: add here also named permissions, i.e. all project.* operations
    hrba.roles[UserRole.GUEST].check["project.workbench.node.inputs.update"] = can_update_node_inputs

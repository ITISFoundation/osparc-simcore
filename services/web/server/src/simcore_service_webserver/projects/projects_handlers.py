
import json
import logging

from aiohttp import web
from jsonschema import ValidationError

from servicelib.application_keys import APP_DB_ENGINE_KEY

from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_api import check_permission
from .projects_api import create_data_from_template, validate_project
from .projects_exceptions import (ProjectInvalidRightsError,
                                  ProjectNotFoundError)
from .projects_fakes import Fake
from .projects_models import ProjectDB

log = logging.getLogger(__name__)


@login_required
async def create_projects(request: web.Request):
    await check_permission(request, "project.create")

    user_id = request[RQT_USERID_KEY]
    db_engine=request.config_dict[APP_DB_ENGINE_KEY]
    template_uuid = request.query.get('from_template')

    try:
        project = {}
        if template_uuid:
            # create from template
            template_prj = await ProjectDB.get_template_project(template_uuid, db_engine)

            if not template_prj: # TODO: inject these projects in db instead!
                for prj in Fake.projects.values():
                    if prj.template and prj.data['uuid']==template_uuid:
                        template_prj = prj.data
                        break
            if not template_prj:
                raise web.HTTPNotFound(reason="Invalid template uuid {}".format(template_uuid))

            project = create_data_from_template(template_prj, user_id)

        # overrides with body
        if request.has_body:
            predefined = await request.json()
            if predefined:
                # FIXME: what to update from predefined??? uuid or timestamps shall not be updated
                for key, value in predefined.items():
                    if value and key not in ("uuid", "lastChangeDate", "creationDate"):
                        project[key] = value

        # validate data
        validate_project(request.app, project)

        # update metadata (uuid, timestamps, ownership) and save
        await ProjectDB.add_project(project, user_id, db_engine)

    except ValidationError:
        raise web.HTTPBadRequest(reason="Invalid project data")

    except ProjectInvalidRightsError:
        raise web.HTTPUnauthorized

    else:
        raise web.HTTPCreated(text=json.dumps(project),
                                content_type='application/json')


@login_required
async def list_projects(request: web.Request):
    await check_permission(request, "project.read")

    # TODO: implement all query parameters as
    # in https://www.ibm.com/support/knowledgecenter/en/SSCRJU_3.2.0/com.ibm.swg.im.infosphere.streams.rest.api.doc/doc/restapis-queryparms-list.html
    user_id = request[RQT_USERID_KEY]
    ptype = request.query.get('type', 'user')

    projects_list = []
    if ptype in ("template", "all"):
        projects_list += [prj.data for prj in Fake.projects.values() if prj.template]
        projects_list += await ProjectDB.load_template_projects(
            db_engine=request.app[APP_DB_ENGINE_KEY]
        )

    if ptype in ("user", "all"):
        projects_list += await ProjectDB.load_user_projects(
            user_id=user_id,
            db_engine=request.app[APP_DB_ENGINE_KEY]
        )

    start = int(request.query.get('start', 0))
    count = int(request.query.get('count',len(projects_list)))

    stop = min(start+count, len(projects_list))
    projects_list = projects_list[start:stop]

    # validate response
    validated_projects = []
    for project in projects_list:
        try:
            validate_project(request.app, project)
            validated_projects.append(project)
        except ValidationError:
            log.exception("Skipping invalid project from list")
            continue

    return {'data': validated_projects}



@login_required
async def get_project(request: web.Request):
    # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
    from .projects_api import get_project_for_user

    project = await get_project_for_user(request,
        project_uuid=request.match_info.get("project_id"),
        user_id=request[RQT_USERID_KEY]
    )

    return {
        'data': project
    }


@login_required
async def replace_project(request: web.Request):
    """ Implements PUT /projects

     In a PUT request, the enclosed entity is considered to be a modified version of
     the resource stored on the origin server, and the client is requesting that the
     stored version be replaced.

     With PATCH, however, the enclosed entity contains a set of instructions describing how a
     resource currently residing on the origin server should be modified to produce a new version.

     Also, another difference is that when you want to update a resource with PUT request, you have to send
     the full payload as the request whereas with PATCH, you only send the parameters which you want to update.

    :raises web.HTTPNotFound: cannot find project id in repository
    """

    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    new_project = await request.json()

    db_engine = request.config_dict[APP_DB_ENGINE_KEY]

    await check_permission(request, "project.update | project.workbench.node.inputs.update",
    context={
        'db_engine': db_engine,
        'project_id': project_uuid,
        'user_id': user_id,
        'new_data': new_project
    })

    try:
        validate_project(request.app, new_project)

        await ProjectDB.update_user_project(new_project, user_id, project_uuid, db_engine)

    except ValidationError:
        raise web.HTTPBadRequest

    except ProjectNotFoundError:
        raise web.HTTPNotFound

    return {'data': new_project}


# TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
#@login_required
#async def patch_project(_request: web.Request):
#    """
#        Client sends a patch and return updated project
#        PATCH
#    """
#    # TODO: implement patch with diff as body!
#    raise NotImplementedError()


@login_required
async def delete_project(request: web.Request):
    # TODO: replace by decorator since it checks again authentication
    await check_permission(request, "project.delete")

    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")

    try:
        await ProjectDB.delete_user_project(user_id, project_uuid, db_engine=request.app[APP_DB_ENGINE_KEY])
    except ProjectNotFoundError:
        raise web.HTTPNotFound

    raise web.HTTPNoContent(content_type='application/json')

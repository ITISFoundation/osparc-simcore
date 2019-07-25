
""" Handlers for CRUD operations on /projects/

"""
import json
import logging

from aiohttp import web
from jsonschema import ValidationError

from ..computation_api import update_pipeline_db
from ..login.decorators import RQT_USERID_KEY, login_required
from ..security_api import check_permission
from ..storage_api import delete_data_folders_of_project
from .projects_api import validate_project
from .projects_db import APP_PROJECT_DBAPI
from .projects_exceptions import (ProjectInvalidRightsError,
                                  ProjectNotFoundError)

OVERRIDABLE_DOCUMENT_KEYS = ['name', 'description', 'thumbnail', 'prjOwner']
# TODO: validate these against api/specs/webserver/v0/components/schemas/project-v0.0.1.json

log = logging.getLogger(__name__)


@login_required
async def create_projects(request: web.Request):
    from .projects_api import clone_project # TODO: keep here since is async and parser thinks it is a handler

    # pylint: disable=too-many-branches
    await check_permission(request, "project.create")
    await check_permission(request, "services.pipeline.*") # due to update_pipeline_db

    user_id = request[RQT_USERID_KEY]
    db = request.config_dict[APP_PROJECT_DBAPI]

    template_uuid = request.query.get('from_template')
    as_template = request.query.get('as_template')

    try:
        project = {}
        if as_template: # create template from
            await check_permission(request, "project.template.create")

            # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
            from .projects_api import get_project_for_user

            source_project = await get_project_for_user(request,
                project_uuid=as_template,
                user_id=user_id,
                include_templates=False
            )
            project = await clone_project(request, source_project, user_id)

        elif template_uuid: # create from template
            template_prj = await db.get_template_project(template_uuid)
            if not template_prj:
                raise web.HTTPNotFound(reason="Invalid template uuid {}".format(template_uuid))

            project = await clone_project(request, template_prj, user_id)
            #FIXME: parameterized inputs should get defaults provided by service

        # overrides with body
        if request.has_body:
            predefined = await request.json()

            if project:
                for key in OVERRIDABLE_DOCUMENT_KEYS:
                    non_null_value = predefined.get(key)
                    if non_null_value:
                        project[key] = non_null_value
            else:
                # TODO: take skeleton and fill instead
                project = predefined

        # validate data
        validate_project(request.app, project)

        # update metadata (uuid, timestamps, ownership) and save
        await db.add_project(project, user_id, force_as_template=as_template is not None)

        # This is a new project and every new graph needs to be reflected in the pipeline db
        await update_pipeline_db(request.app, project["uuid"], project["workbench"])

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
    ptype = request.query.get('type', 'all') # TODO: get default for oaspecs
    db = request.config_dict[APP_PROJECT_DBAPI]

    # TODO: improve dbapi to list project
    projects_list = []
    if ptype in ("template", "all"):
        projects_list += await db.load_template_projects()

    if ptype in ("user", "all"): # standard only (notice that templates will only)
        projects_list += await db.load_user_projects(user_id=user_id, exclude_templates=True)

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
    """ Returns all projects accessible to a user (not necesarly owned)

    """
    # TODO: temporary hidden until get_handlers_from_namespace refactor to seek marked functions instead!
    from .projects_api import get_project_for_user

    project_uuid = request.match_info.get("project_id")

    project = await get_project_for_user(request,
        project_uuid=project_uuid,
        user_id=request[RQT_USERID_KEY],
        include_templates=True
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
    await check_permission(request, "services.pipeline.*") # due to update_pipeline_db

    user_id = request[RQT_USERID_KEY]
    project_uuid = request.match_info.get("project_id")
    replace_pipeline = request.match_info.get("run", False)
    new_project = await request.json()


    db = request.config_dict[APP_PROJECT_DBAPI]
    await check_permission(request, "project.update | project.workbench.node.inputs.update",
    context={
        'dbapi': db,
        'project_id': project_uuid,
        'user_id': user_id,
        'new_data': new_project
    })

    try:
        validate_project(request.app, new_project)

        await db.update_user_project(new_project, user_id, project_uuid)

        await update_pipeline_db(request.app, project_uuid, new_project["workbench"], replace_pipeline)

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
    db = request.config_dict[APP_PROJECT_DBAPI]

    try:
        # TODO: delete pipeline db tasks
        await db.delete_user_project(user_id, project_uuid)

    except ProjectNotFoundError:
        # TODO: add flag in query to determine whether to respond if error?
        raise web.HTTPNotFound

    # requests storage to delete all project's stored data
    # TODO: fire & forget
    await delete_data_folders_of_project(request.app, project_uuid, user_id)


    # TODO: delete all the dynamic services used by this project when this happens (fire & forget) #
    # import asyncio
    # from ..director.director_api import stop_service
    # project = await db.pop_project(project_uuid)
    # tasks = [ stop_service(request.app, service_uuid) for service_uuid in  project.get('workbench',[]) ]
    # await asyncio.gather(**tasks)
    # TODO: fire&forget???

    raise web.HTTPNoContent(content_type='application/json')

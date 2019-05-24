"""
    Uses socketio and aiohtttp framework

    TODO: move into submodule computational_backend
"""
# pylint: disable=C0103

import datetime
import logging
from typing import Dict

import sqlalchemy as sa
from aiohttp import web, web_exceptions
from aiopg.sa import Engine
from celery import Celery
from sqlalchemy import and_

from servicelib.application_keys import APP_CONFIG_KEY, APP_DB_ENGINE_KEY
from servicelib.request_keys import RQT_USERID_KEY
from simcore_director_sdk.rest import ApiException
from simcore_sdk.config.rabbit import Config as rabbit_config
from simcore_sdk.models.pipeline_models import (ComputationalPipeline,
                                                ComputationalTask)

from .computation_config import CONFIG_SECTION_NAME as CONFIG_RABBIT_SECTION
from .director import director_sdk
from .login.decorators import login_required
from .projects import projects_handlers
from .security_api import check_permission

ANONYMOUS_USER_ID = -1


log = logging.getLogger(__file__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


computation_routes = web.RouteTableDef()

def get_celery(_app: web.Application):
    config = _app[APP_CONFIG_KEY][CONFIG_RABBIT_SECTION]
    rabbit = rabbit_config(config=config)
    celery = Celery(rabbit.name, broker=rabbit.broker, backend=rabbit.backend)
    return celery

async def _get_node_details(node_key:str, node_version:str, app: web.Application)->dict:
    if "file-picker" in node_key:
        # create a fake file-picker schema here!!
        fake_node_details = {"inputs":{},
                        "outputs":{
                            "outFile":{
                                "label":"the output",
                                "displayOrder":0,
                                "description":"a file",
                                "type":"data:*/*"
                            }
                        },
                        "type":"dynamic"
            }
        return fake_node_details
    if "StimulationSelectivity" in node_key:
        # create a fake file-picker schema here!!
        fake_node_details = {"inputs":{},
                        "outputs":{
                            "stimulationFactor":{
                                "label":"the output",
                                "displayOrder":0,
                                "description":"a file",
                                "type":"data:*/*",
                                "defaultValue": 0.6
                            }
                        },
                        "type":"dynamic"
            }
        return fake_node_details
    try:
        services_enveloped = await director_sdk.create_director_api_client(app).services_by_key_version_get(node_key, node_version)
        node_details = services_enveloped.data[0].to_dict()
        return node_details
    except ApiException as err:
        log.exception("Error could not find service %s:%s", node_key, node_version)
        raise web_exceptions.HTTPNotFound(reason=str(err))

async def _build_adjacency_list(node_uuid:str, node_schema:dict, node_inputs:dict, pipeline_data:dict, dag_adjacency_list:dict, app: web.Application)->dict: # pylint: disable=too-many-arguments
    if node_inputs is None or node_schema is None:
        return dag_adjacency_list

    for _, input_data in node_inputs.items():
        if input_data is None:
            continue
        is_node_computational = (node_schema["type"] == "computational")
        # add it to the list
        if is_node_computational and node_uuid not in dag_adjacency_list:
            dag_adjacency_list[node_uuid] = []

        # check for links
        if isinstance(input_data, dict) and all(k in input_data for k in ("nodeUuid", "output")):
            log.debug("decoding link %s", input_data)
            input_node_uuid = input_data["nodeUuid"]
            if "demodec" in pipeline_data[input_node_uuid]["key"]:
                continue
            input_node_details = await _get_node_details(pipeline_data[input_node_uuid]["key"], pipeline_data[input_node_uuid]["version"], app)
            log.debug("input node details %s", input_node_details)
            if input_node_details is None:
                continue
            is_predecessor_computational = (input_node_details["type"] == "computational")
            if is_predecessor_computational:
                if input_node_uuid not in dag_adjacency_list:
                    dag_adjacency_list[input_node_uuid] = []
                if node_uuid not in dag_adjacency_list[input_node_uuid] and is_node_computational:
                    dag_adjacency_list[input_node_uuid].append(node_uuid)
    return dag_adjacency_list

async def _parse_pipeline(pipeline_data:dict, app: web.Application): # pylint: disable=R0912
    dag_adjacency_list = dict()
    tasks = dict()

    #TODO: we should validate all these things before processing...
    for node_uuid, value in pipeline_data.items():
        if not all(k in value for k in ("key", "version")):
            log.debug("skipping workbench entry containing %s:%s", node_uuid, value)
            continue
        node_key = value["key"]
        node_version = value["version"]

        # get the task data
        node_inputs = None
        if "inputs" in value:
            node_inputs = value["inputs"]
        node_outputs = None
        if "outputs" in value:
            node_outputs = value["outputs"]
        log.debug("node %s:%s has inputs: \n%s\n outputs: \n%s", node_key, node_version, node_inputs, node_outputs)

        # HACK: skip fake services
        if "demodec" in node_key:
            log.debug("skipping workbench entry containing %s:%s", node_uuid, value)
            continue
        node_details = await _get_node_details(node_key, node_version, app)
        log.debug("node %s:%s has schema:\n %s",node_key, node_version, node_details)
        dag_adjacency_list = await _build_adjacency_list(node_uuid, node_details, node_inputs, pipeline_data, dag_adjacency_list, app)
        log.debug("node %s:%s list updated:\n %s",node_key, node_version, dag_adjacency_list)

        # create the task
        node_schema = None
        if not node_details is None:
            node_schema = {"inputs":node_details["inputs"], "outputs":node_details["outputs"]}
        task = {
            "schema":node_schema,
            "inputs":node_inputs,
            "outputs":node_outputs,
            "image":{
                "name":node_key,
                "tag":node_version
            }
        }

        log.debug("storing task for node %s: %s", node_uuid, task)
        tasks[node_uuid] = task
        log.debug("task stored")
    return dag_adjacency_list, tasks

async def _set_adjacency_in_pipeline_db(db_engine: Engine, project_id: str, dag_adjacency_list: Dict):
    async with db_engine.acquire() as conn:
        query = sa.select([ComputationalPipeline]).\
                    where(ComputationalPipeline.__table__.c.project_id==project_id)
        result = await conn.execute(query)
        pipeline = await result.first()

        if pipeline is None:
            # let's create one then
            query = ComputationalPipeline.__table__.insert().\
                    values(project_id=project_id,
                            dag_adjacency_list=dag_adjacency_list,
                            state=0)

            log.debug("Pipeline object created")
        else:
            # let's modify it
            log.debug("Pipeline object found")
            query = ComputationalPipeline.__table__.update().\
                        where(ComputationalPipeline.__table__.c.project_id == project_id).\
                        values(state=0,
                                dag_adjacency_list=dag_adjacency_list)
        await conn.execute(query)

async def _set_tasks_in_tasks_db(db_engine: Engine, project_id: str, tasks: Dict):
    async with db_engine.acquire() as conn:
        query = sa.select([ComputationalTask]).\
                where(ComputationalTask.__table__.c.project_id == project_id)
        result = await conn.execute(query)
        tasks_db = await result.fetchall()
        # delete tasks that were deleted from the db
        for task_db in tasks_db:
            if not task_db.node_id in tasks:
                query = ComputationalTask.__table__.delete().\
                        where(and_(ComputationalTask.__table__.c.project_id == project_id,
                                    ComputationalTask.__table__.c.node_id == task_db.node_id))
                await conn.execute(query)
        internal_id = 1
        for node_id in tasks:
            task = tasks[node_id]
            query = sa.select([ComputationalTask]).\
                    where(and_(ComputationalTask.__table__.c.project_id == project_id,
                                ComputationalTask.__table__.c.node_id == node_id))
            result = await conn.execute(query)
            comp_task = await result.fetchone()
            if comp_task is None:
                # add a new one
                query = ComputationalTask.__table__.insert().\
                        values(project_id=project_id,
                                node_id=node_id,
                                internal_id=internal_id,
                                image = task["image"],
                                schema = task["schema"],
                                inputs = task["inputs"],
                                outputs = task["outputs"],
                                submit = datetime.datetime.utcnow())
                internal_id = internal_id+1
            else:
                query = ComputationalTask.__table__.update().\
                        where(and_(ComputationalTask.__table__.c.project_id==project_id,
                                ComputationalTask.__table__.c.node_id==node_id)).\
                        values(job_id = None,
                                state = 0,
                                image = task["image"],
                                schema = task["schema"],
                                inputs = task["inputs"],
                                outputs = task["outputs"] if "file-picker" in task["image"]["name"] else comp_task.outputs,
                                submit = datetime.datetime.utcnow())
            await conn.execute(query)

async def _update_pipeline_db(app: web.Application, project_id, pipeline_data):
    db_engine = app[APP_DB_ENGINE_KEY]

    log.debug("Client calls update_pipeline with project id: %s, pipeline data %s", project_id, pipeline_data)
    dag_adjacency_list, tasks = await _parse_pipeline(pipeline_data, app)
    log.debug("Pipeline parsed:\nlist: %s\ntasks: %s", str(dag_adjacency_list), str(tasks))
    await _set_adjacency_in_pipeline_db(db_engine, project_id, dag_adjacency_list)
    await _set_tasks_in_tasks_db(db_engine, project_id, tasks)
    log.debug("END OF ROUTINE.")

# HANDLERS ------------------------------------------

async def _patch_project(request: web.Request, project_id, pipeline_data):
    #FIXME: do NOT use handlers ... really unsafe. Create API instead

    # update = get+patch+replace project
    new_request = request.clone(
        rel_url=request.app.router['get_project'].url_for(project_id=project_id)
    )

    #FIXME: read project 'Content-Length': '0'
    payload = await projects_handlers.get_project(new_request)
    project = payload["data"] # FIXME: this is not safe!!!!


    if pipeline_data and project["workbench"] != pipeline_data:
        # FIXME: patch json assuming project has the right format
        project["workbench"] = pipeline_data

        new_request = request.clone(
            rel_url=request.app.router['replace_project'].url_for(project_id=project_id)
        )
        await projects_handlers.replace_project(new_request)
    else:
        pipeline_data = project["workbench"]

    return pipeline_data




@login_required
async def update_pipeline(request: web.Request) -> web.Response:
    await check_permission(request, "services.pipeline.*")

    # TODO: PC->SAN why validation is commented???
    # params, query, body = await extract_and_validate(request)
    project_id = request.match_info.get("project_id", None)
    assert project_id is not None

    pipeline_data = (await request.json())["workbench"]

    await _patch_project(request, project_id, pipeline_data)

    # update pipeline
    await _update_pipeline_db(request.app, project_id, pipeline_data)

    raise web.HTTPNoContent()


# pylint:disable=too-many-branches, too-many-statements
@login_required
async def start_pipeline(request: web.Request) -> web.Response:
    await check_permission(request, "services.pipeline.*")

    # TODO: PC->SAN why validation is commented???
    # params, query, body = await extract_and_validate(request)
    project_id = request.match_info.get("project_id", None)
    assert project_id is not None

    # if different workbench
    payload = await request.json()
    pipeline_data = payload.get("workbench") if payload else None
    pipeline_data = await _patch_project(request, project_id, pipeline_data)

    await _update_pipeline_db(request.app, project_id, pipeline_data)

    # commit the tasks to celery
    userid = request.get(RQT_USERID_KEY, ANONYMOUS_USER_ID)
    _ = get_celery(request.app).send_task("comp.task", args=(userid, project_id,), kwargs={})

    log.debug("Task commited")

    # answer the client while task has been spawned
    data = {
        # TODO: PC->SAN: some name with task id. e.g. to distinguish two projects with identical pipeline?
        "pipeline_name":"request_data",
        "project_id": project_id
    }
    log.debug("END OF ROUTINE. Response %s", data)
    return data

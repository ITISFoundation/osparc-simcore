"""
    Uses socketio and aiohtttp framework

    TODO: move into submodule computational_backend
"""
# pylint: disable=C0103

import asyncio
import datetime
import logging

import sqlalchemy.exc
from aiohttp import web, web_exceptions
from sqlalchemy import and_, create_engine
from sqlalchemy.orm import sessionmaker

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.request_keys import RQT_USERID_KEY
from simcore_director_sdk.rest import ApiException
from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)

from .computation_worker import celery
from .db_config import CONFIG_SECTION_NAME as CONFIG_DB_SECTION
from .director import director_sdk
from .login.decorators import login_required

# TODO: this should be coordinated with postgres options from config/server.yaml
#from simcore_sdk.config.db import Config as DbConfig
#from simcore_sdk.config.s3 import Config as S3Config
#-------------------------------------------------------------



log = logging.getLogger(__file__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


db_session = None
computation_routes = web.RouteTableDef()

async def init_database(_app):
    #pylint: disable=W0603
    global db_session

    # TODO: use here persist module to keep everything homogeneous
    RETRY_WAIT_SECS = 2
    RETRY_COUNT = 20

    # db config
    db_config = _app[APP_CONFIG_KEY][CONFIG_DB_SECTION]["postgres"]
    endpoint = "postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}".format(**db_config)

    db_engine = create_engine(endpoint,
        client_encoding="utf8",
        connect_args={"connect_timeout": 30},
        pool_pre_ping=True)

    # FIXME: the db tables are created here, this only works when postgres is up and running.
    # For now lets just try a couple of times.
    # This should NOT be executed upon importing the module but as a separate function that is called async
    # upon initialization of the web app (e.g. like subscriber)
    # The system should not stop because session is not connect. it should report error when a db operation
    # is required but not stop the entire application.
    DatabaseSession = sessionmaker(db_engine)
    db_session = DatabaseSession()
    for i in range(RETRY_COUNT):
        try:
            Base.metadata.create_all(db_engine)
        except sqlalchemy.exc.SQLAlchemyError as err:
            await asyncio.sleep(RETRY_WAIT_SECS)
            msg = "Retrying to create database %d/%d ..." % (i+1, RETRY_COUNT)
            log.warning("%s: %s", str(err), msg)
            print("oops " + msg)

async def _get_node_details(node_key:str, node_version:str)->dict:
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
    try:
        services_enveloped = await director_sdk.get_director().services_by_key_version_get(node_key, node_version)
        node_details = services_enveloped.data[0].to_dict()
        return node_details
    except ApiException as err:
        log.exception("Error could not find service %s:%s", node_key, node_version)
        raise web_exceptions.HTTPNotFound(reason=str(err))

async def _build_adjacency_list(node_uuid:str, node_schema:dict, node_inputs:dict, pipeline_data:dict, dag_adjacency_list:dict)->dict:
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
            input_node_details = await _get_node_details(pipeline_data[input_node_uuid]["key"], pipeline_data[input_node_uuid]["version"])
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

async def _parse_pipeline(pipeline_data:dict): # pylint: disable=R0912
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
        node_details = await _get_node_details(node_key, node_version)
        log.debug("node %s:%s has schema:\n %s",node_key, node_version, node_details)
        dag_adjacency_list = await _build_adjacency_list(node_uuid, node_details, node_inputs, pipeline_data, dag_adjacency_list)
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

async def _set_adjacency_in_pipeline_db(project_id, dag_adjacency_list):
    try:
        pipeline = db_session.query(ComputationalPipeline).filter(ComputationalPipeline.project_id==project_id).one()
        log.debug("Pipeline object found")
        pipeline.state = 0
        pipeline.dag_adjacency_list = dag_adjacency_list
    except sqlalchemy.orm.exc.NoResultFound:
        # let's create one then
        pipeline = ComputationalPipeline(project_id=project_id, dag_adjacency_list=dag_adjacency_list, state=0)
        log.debug("Pipeline object created")
        db_session.add(pipeline)
    except sqlalchemy.orm.exc.MultipleResultsFound:
        log.exception("the computation pipeline %s is not unique", project_id)
        raise

async def _set_tasks_in_tasks_db(project_id, tasks):
    tasks_db = db_session.query(ComputationalTask).filter(ComputationalTask.project_id==project_id).all()
    # delete tasks that were deleted from the db
    for task_db in tasks_db:
        if not task_db.node_id in tasks:
            db_session.delete(task_db)
    internal_id = 1
    for node_id in tasks:
        task = tasks[node_id]
        try:
            comp_task = db_session.query(ComputationalTask).filter(and_(ComputationalTask.project_id==project_id, ComputationalTask.node_id==node_id)).one()
            comp_task.job_id = None
            comp_task.state = 0
            comp_task.image = task["image"]
            comp_task.schema = task["schema"]
            comp_task.inputs = task["inputs"]
            comp_task.outputs = task["outputs"]
            comp_task.submit = datetime.datetime.utcnow()
        except sqlalchemy.orm.exc.NoResultFound:
            comp_task = ComputationalTask( \
                project_id=project_id,
                node_id=node_id,
                internal_id=internal_id,
                image=task["image"],
                schema=task["schema"],
                inputs=task["inputs"],
                outputs=task["outputs"],
                submit=datetime.datetime.utcnow()
                )
            internal_id = internal_id+1
            db_session.add(comp_task)

# pylint:disable=too-many-branches, too-many-statements
@login_required
async def start_pipeline(request: web.Request) -> web.Response:
    #pylint:disable=broad-except
    # FIXME: this should be implemented generaly using async lazy initialization of db_session??
    #pylint: disable=W0603
    global db_session
    if db_session is None:
        await init_database(request.app)

    # params, query, body = await extract_and_validate(request)
    
    # if params is not None:
    #     log.debug("params: %s", params)
    # if query is not None:
    #     log.debug("query: %s", query)
    # if body is not None:
    #     log.debug("body: %s", body)

    # assert "project_id" in params
    # assert "workbench" in body

    # retrieve the data
    project_id = request.match_info.get("project_id", None)
    assert project_id is not None
    pipeline_data = (await request.json())["workbench"]
    userid = request[RQT_USERID_KEY]
    _app = request.app[APP_CONFIG_KEY]

    log.debug("Client calls start_pipeline with project id: %s, pipeline data %s", project_id, pipeline_data)
    dag_adjacency_list, tasks = await _parse_pipeline(pipeline_data)
    log.debug("Pipeline parsed:\nlist: %s\ntasks: %s", str(dag_adjacency_list), str(tasks))
    try:
        await _set_adjacency_in_pipeline_db(project_id, dag_adjacency_list)
        await _set_tasks_in_tasks_db(project_id, tasks)
        db_session.commit()
        # commit the tasks to celery
        _ = celery.send_task("comp.task", args=(userid, project_id,), kwargs={})
        log.debug("Task commited")
        # answer the client
        pipeline_name = "request_data"
        response = {
        "pipeline_name":pipeline_name,
        "project_id": project_id
        }
        log.debug("END OF ROUTINE. Response %s", response)
        return web.json_response(response, status=201)
    except sqlalchemy.exc.InvalidRequestError as err:
        log.exception("Alchemy error: Invalid request. Rolling back db.")
        db_session.rollback()
        raise web_exceptions.HTTPInternalServerError(reason=str(err)) from err
    except sqlalchemy.exc.SQLAlchemyError as err:
        log.exception("Alchemy error: General error. Rolling back db.")
        db_session.rollback()
        raise web_exceptions.HTTPInternalServerError(reason=str(err)) from err
    except Exception as err:
        log.exception("Unexpected error.")
        raise web_exceptions.HTTPInternalServerError(reason=str(err)) from err
    finally:
        log.debug("Close session")
        db_session.close()

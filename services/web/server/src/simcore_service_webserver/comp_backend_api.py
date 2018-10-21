"""
    Uses socketio and aiohtttp framework

    TODO: move into submodule computational_backend
"""
# pylint: disable=C0103

import asyncio
import datetime
import logging

import async_timeout
import sqlalchemy.exc
from aiohttp import web, web_exceptions
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from s3wrapper.s3_client import S3Client
from simcore_sdk.models.pipeline_models import (Base, ComputationalPipeline,
                                                ComputationalTask)

from . import api_converter
from .comp_backend_worker import celery
from .application_keys import APP_CONFIG_KEY

# TODO: this should be coordinated with postgres options from config/server.yaml
#from simcore_sdk.config.db import Config as DbConfig
#from simcore_sdk.config.s3 import Config as S3Config
#-------------------------------------------------------------



log = logging.getLogger(__file__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


db_session = None
comp_backend_routes = web.RouteTableDef()

async def init_database(_app):
    #pylint: disable=W0603
    global db_session

    # TODO: use here persist module to keep everything homogeneous
    RETRY_WAIT_SECS = 2
    RETRY_COUNT = 20

    # db config
    db_config = _app[APP_CONFIG_KEY]["postgres"]
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


async def async_request(method, session, url, data=None, timeout=10):
    async with async_timeout.timeout(timeout):
        if method == "GET":
            async with session.get(url) as response:
                return await response.json()
        elif method == "POST":
            async with session.post(url, json=data) as response:
                return await response.json()
        # TODO: else raise ValueError method not implemented?

async def _parse_pipeline(pipeline_data): # pylint: disable=R0912
    dag_adjacency_list = dict()
    tasks = dict()
    io_files = []

    for key, value in pipeline_data.items():
        if not all(k in value for k in ("key", "version", "inputs", "outputs")):
            log.debug("skipping workbench entry containing %s:%s", key, value)
            continue
        node_uuid = key
        node_key = value["key"]
        node_version = value["version"]
        node_inputs = value["inputs"]
        node_outputs = value["outputs"]
        log.debug("node %s:%s has inputs: \n%s\n outputs: \n%s", node_key, node_version, node_inputs, node_outputs)
        #TODO: we should validate all these things before processing...

        # build computational adjacency list for sidecar
        for input_data in node_inputs.values():
            is_node_computational = (str(node_key).count("/comp/") > 0)
            # add it to the list
            if is_node_computational and node_uuid not in dag_adjacency_list:
                dag_adjacency_list[node_uuid] = []

            # check for links
            if not isinstance(input_data, dict):
                continue
            if "nodeUuid" in input_data and "output" in input_data:
                input_node_uuid = input_data["nodeUuid"]
                is_predecessor_computational = (pipeline_data[input_node_uuid]["key"].count("/comp/") > 0)
                if is_predecessor_computational:
                    if input_node_uuid not in dag_adjacency_list:
                        dag_adjacency_list[input_node_uuid] = []
                    if node_uuid not in dag_adjacency_list[input_node_uuid] and is_node_computational:
                        dag_adjacency_list[input_node_uuid].append(node_uuid)

        for output_key, output_data in node_outputs.items():
            if not isinstance(output_data, dict):
                continue
            if all(k in output_data for k in ("store", "path")):
                if output_data["store"] == "s3-z43":
                    current_filename_on_s3 = output_data["path"]
                    if current_filename_on_s3:
                        new_filename = key + "/" + output_key # in_1
                        # copy the file
                        io_files.append({ "from" : current_filename_on_s3, "to" : new_filename })

        # create the task
        task = {
            "input":node_inputs,
            "output":node_outputs,
            "image":{
                "name":node_key,
                "tag":node_version
            }
        }

        # currently here a special case to handle the built-in file manager that should not be set as a task
        if str(node_key).count("file-picker") == 0:
            # TODO: SAN This is temporary. As soon as the services are converted this should be removed.
            task = await api_converter.convert_task_to_old_version(task)
        #     continue


        log.debug("storing task in node is %s: %s", node_uuid, task)
        tasks[node_uuid] = task
        log.debug("task stored")
    log.debug("converted all tasks: \nadjacency list: %s\ntasks: %s\nio_files: %s", dag_adjacency_list, tasks, io_files)
    return dag_adjacency_list, tasks, io_files

async def _transfer_data(app, pipeline_id, io_files):
    if io_files:
        _config = app["s3"]

        s3_client = S3Client(endpoint=_config['endpoint'], access_key=_config['access_key'], secret_key=_config['secret_key'])
        for io_file in io_files:
            _from = io_file["from"]
            _to = str(pipeline_id) + "/" + io_file["to"]
            log.debug("COPYING from %s to %s", _from, _to )
            #TODO: make async?
            s3_client.copy_object(_config['bucket_name'], _to, _from)

# pylint:disable=too-many-branches, too-many-statements
@comp_backend_routes.post("/start_pipeline")
async def start_pipeline(request):
    #pylint:disable=broad-except

    """
    ---
    description: This end-point starts a computational pipeline.
    tags:
    - services management
    produces:
    - application/json
    responses:
        "200":
            description: successful operation
        "405":
            description: invalid HTTP Method
    """
    # FIXME: this should be implemented generaly using async lazy initialization of db_session??
    #pylint: disable=W0603
    global db_session
    if db_session is None:
        await init_database(request.app)
    request_data = await request.json()

    log.debug("Client calls start_pipeline with %s", request_data)
    _app = request.app[APP_CONFIG_KEY]
    log.debug("Parse pipeline %s", _app)
    dag_adjacency_list, tasks, io_files = await _parse_pipeline(request_data)
    log.debug("Pipeline parsed:\nlist: %s\ntasks: %s\n io_files %s", str(dag_adjacency_list), str(tasks), str(io_files))
    try:
        # create the new pipeline in db
        pipeline = ComputationalPipeline(dag_adjacency_list=dag_adjacency_list, state=0)
        log.debug("Pipeline object created")
        db_session.add(pipeline)
        log.debug("Pipeline object added")
        db_session.flush()
        log.debug("Pipeline flushed")
        pipeline_id = pipeline.pipeline_id

        # now we know the id, lets copy over data
        await _transfer_data(_app, pipeline_id, io_files)
        # create the tasks in db
        pipeline_name = "request_data"
        internal_id = 1
        for node_id in tasks:
            task = tasks[node_id]
            new_task = ComputationalTask( \
                pipeline_id=pipeline_id,
                node_id=node_id,
                internal_id=internal_id,
                image=task["image"],
                input=task["input"],
                output=task["output"],
                submit=datetime.datetime.utcnow()
                )
            internal_id = internal_id+1
            db_session.add(new_task)
        db_session.commit()
        # commit the tasks to celery
        task = celery.send_task("comp.task", args=(pipeline_id,), kwargs={})
        log.debug("Task commited")
        # answer the client
        response = {
        "pipeline_name":pipeline_name,
        "pipeline_id":str(pipeline_id)
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

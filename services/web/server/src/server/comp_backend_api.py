"""
    Uses socketio and aiohtttp framework

    TODO: move into submodule computational_backend
"""
# pylint: disable=C0103

import datetime
import logging
import asyncio

import async_timeout
from aiohttp import web
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sqlalchemy.exc

from s3wrapper.s3_client import S3Client
# TODO: this should be coordinated with postgres options from config/server.yaml
#from simcore_sdk.config.db import Config as DbConfig
#from simcore_sdk.config.s3 import Config as S3Config
#-------------------------------------------------------------

from simcore_sdk.models.pipeline_models import (
    Base,
    ComputationalPipeline,
    ComputationalTask
)

from .comp_backend_worker import celery

_LOGGER = logging.getLogger(__file__)
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
    db_config = _app["config"]["postgres"]
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
            _LOGGER.warning("%s: %s", str(err), msg)
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

# pylint:disable=too-many-branches, too-many-statements
@comp_backend_routes.post("/start_pipeline")
async def start_pipeline(request):
    #pylint:disable=broad-except

    """
    ---
    description: This end-point starts a computational pipeline.
    tags:
    - computational backend
    produces:
    - application/json
    responses:
        "200":
            description: successful operation. Return "pong" text
        "405":
            description: invalid HTTP Method
    """
    # FIXME: this should be implemented generaly using async lazy initialization of db_session??
    #pylint: disable=W0603
    global db_session
    if db_session is None:
        await init_database(request.app)

    request_data = await request.json()

    _app = request.app["config"]
    response = {}

    nodes = request_data["nodes"]
    links = request_data["links"]

    dag_adjacency_list = dict()
    tasks = dict()

    pipeline_id = -1
    pipeline_name = "New pipeline"
    _LOGGER.debug("Start Pipeline")

    # pylint: disable=too-many-nested-blocks
    try:
        io_files = []
        for node in nodes:
            _LOGGER.debug("NODE %s ", node)

            node_id = node["uuid"]
            # find connections
            successor_nodes = []
            task = {}
            is_io_node = False
            if node["key"] == "FileManager":
                is_io_node = True

            task["input"] = node["inputs"]
            task["output"] = node["outputs"]
            task["image"] = {"name" : node["key"], "tag"  : node["tag"]}

            if is_io_node:
                for ofile in node["outputs"]:
                    current_filename_on_s3 = ofile["value"]
                    if current_filename_on_s3:
                        new_filename = node_id +"/" + ofile["key"] # out_1
                        # copy the file
                        io_files.append({ "from" : current_filename_on_s3, "to" : new_filename })

            for link in links:
                if link["node1Id"] == node_id:
                    successor_node_id = link["node2Id"]
                    if successor_node_id not in successor_nodes and not is_io_node:
                        successor_nodes.append(successor_node_id)
                if link["node2Id"] == node_id:
                    # there might be something coming in
                    predecessor_node_id = link["node1Id"]
                    output_port = link["port1Id"]
                    input_port = link["port2Id"]
                    # we use predecessor_node_id.output_port as id fo the input
                    for t in task["input"]:
                        if t["key"] == input_port:
                            t["value"] = "link." + predecessor_node_id + "." + output_port

            if not is_io_node:
                # a node can have an empty successor
                #if len(successor_nodes):
                dag_adjacency_list[node_id] = successor_nodes
                tasks[node_id] = task

        _LOGGER.debug("Pipeline parsed")

        pipeline = ComputationalPipeline(dag_adjacency_list=dag_adjacency_list, state=0)
        _LOGGER.debug("Pipeline object created")

        db_session.add(pipeline)
        _LOGGER.debug("Pipeline object added")

        db_session.flush()
        _LOGGER.debug("Pipeline flushed")

        pipeline_id = pipeline.pipeline_id

        # now we know the id, lets copy over data
        if io_files:
            _config = _app["config"]["s3"]

            s3_client = S3Client(endpoint=_config['endpoint'],
                access_key=_config['access_key'], secret_key=_config['secret_key'])
            for io_file in io_files:
                _from = io_file["from"]
                _to = str(pipeline_id) + "/" + io_file["to"]
                _LOGGER.debug("COPYING from %s to %s", _from, _to )

                s3_client.copy_object(_config['bucket_name'], _to, _from)


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

        task = celery.send_task("comp.task", args=(pipeline_id,), kwargs={})
        _LOGGER.debug("Task commited")

    except sqlalchemy.exc.SQLAlchemyError:
        _LOGGER.exception("Alchemy error. Rolling backe and returning pipeline_id=-1")
        db_session.rollback()
        pipeline_id = -1

    except Exception:
        _LOGGER.exception("Unexpected Exception. Returning pipeline_id=-1")
        pipeline_id = -1

    finally:
        _LOGGER.debug("Close session")
        db_session.close()

    _LOGGER.debug("END OF ROUTINE. Response %s", response)
    response['pipeline_name'] = pipeline_name
    response['pipeline_id'] = str(pipeline_id)

    return web.json_response(response)

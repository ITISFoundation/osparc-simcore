""" API of computation subsystem within this application

"""
import datetime
import logging
from pprint import pformat
from typing import Dict

import sqlalchemy as sa
from aiohttp import web, web_exceptions
from aiopg.sa import Engine
from servicelib.application_keys import APP_DB_ENGINE_KEY
from simcore_director_sdk.rest import ApiException
from simcore_postgres_database.webserver_models import (comp_pipeline,
                                                        comp_tasks)
from sqlalchemy import and_

from .director import director_sdk

log = logging.getLogger(__file__)
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)


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
        log.debug("node %s:%s has schema:\n %s",node_key, node_version, pformat(node_details))
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
        query = sa.select([comp_pipeline]).\
                    where(comp_pipeline.c.project_id==project_id)
        result = await conn.execute(query)
        pipeline = await result.first()

        if pipeline is None:
            # pylint: disable=no-value-for-parameter
            # let's create one then
            query = comp_pipeline.insert().\
                    values(project_id=project_id,
                            dag_adjacency_list=dag_adjacency_list,
                            state=0)

            log.debug("Pipeline object created")
        else:
            # let's modify it
            log.debug("Pipeline object found")
            #pylint: disable=no-value-for-parameter
            query = comp_pipeline.update().\
                        where(comp_pipeline.c.project_id == project_id).\
                        values(state=0,
                                dag_adjacency_list=dag_adjacency_list)
        await conn.execute(query)

async def _set_tasks_in_tasks_db(db_engine: Engine, project_id: str, tasks: Dict):
    async with db_engine.acquire() as conn:
        query = sa.select([comp_tasks]).\
                where(comp_tasks.c.project_id == project_id)
        result = await conn.execute(query)
        tasks_db = await result.fetchall()
        # delete tasks that were deleted from the db
        for task_db in tasks_db:
            if not task_db.node_id in tasks:
                #pylint: disable=no-value-for-parameter
                query = comp_tasks.delete().\
                        where(and_(comp_tasks.c.project_id == project_id,
                                    comp_tasks.c.node_id == task_db.node_id))
                await conn.execute(query)
        internal_id = 1
        for node_id in tasks:
            task = tasks[node_id]
            #pylint: disable=no-value-for-parameter
            query = sa.select([comp_tasks]).\
                    where(and_(comp_tasks.c.project_id == project_id,
                                comp_tasks.c.node_id == node_id))
            result = await conn.execute(query)
            comp_task = await result.fetchone()
            if comp_task is None:
                # add a new one
                #pylint: disable=no-value-for-parameter
                query = comp_tasks.insert().\
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
                #pylint: disable=no-value-for-parameter
                query = comp_tasks.update().\
                        where(and_(comp_tasks.c.project_id==project_id,
                                comp_tasks.c.node_id==node_id)).\
                        values(job_id = None,
                                state = 0,
                                image = task["image"],
                                schema = task["schema"],
                                inputs = task["inputs"],
                                outputs = task["outputs"] if "file-picker" in task["image"]["name"] else comp_task.outputs,
                                submit = datetime.datetime.utcnow())
            await conn.execute(query)

# API ------------------------------------------

async def update_pipeline_db(app: web.Application, project_id, pipeline_data):
    db_engine = app[APP_DB_ENGINE_KEY]

    log.debug("Client calls update_pipeline with project id: %s, pipeline data %s", project_id, pipeline_data)
    dag_adjacency_list, tasks = await _parse_pipeline(pipeline_data, app)

    log.debug("Pipeline parsed:\nlist: %s\ntasks: %s", str(dag_adjacency_list), str(tasks))
    await _set_adjacency_in_pipeline_db(db_engine, project_id, dag_adjacency_list)
    await _set_tasks_in_tasks_db(db_engine, project_id, tasks)

    log.debug("END OF ROUTINE.")

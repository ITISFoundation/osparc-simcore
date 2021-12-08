# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from http import HTTPStatus
from pathlib import Path
from typing import Dict, Union

import pytest
from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient
from models_library.database_project_models import (
    ProjectForPgInsert,
    load_projects_exported_as_csv,
)
from models_library.projects import Project
from pytest_simcore.simcore_webserver_projects_rest_api import (
    NEW_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    RUN_PROJECT,
)
from simcore_service_webserver.meta_handlers import Page, ProjectIterationAsItem

JSON_KWARGS = dict(indent=2, sort_keys=True)


async def test_iterators_workflow(client: TestClient):
    resp: ClientResponse

    # new project --------------------------------------------------------------
    assert NEW_PROJECT.request_desc == "POST /projects"
    resp = await client.request(
        NEW_PROJECT.method, NEW_PROJECT.path, json=NEW_PROJECT.request_payload
    )
    assert resp.status == NEW_PROJECT.status_code

    # create meta-project: iterator 0:3 -> sleeper -> sleeper_2 ---------------
    assert (
        REPLACE_PROJECT_ON_MODIFIED.request_desc
        == "PUT /projects/18f1938c-567d-11ec-b2f3-02420a000010"
    )
    resp = await client.request(
        REPLACE_PROJECT_ON_MODIFIED.method,
        REPLACE_PROJECT_ON_MODIFIED.path,
        json=REPLACE_PROJECT_ON_MODIFIED.request_payload,
    )
    assert resp.status == REPLACE_PROJECT_ON_MODIFIED.status_code

    # TODO: create iterations, so user could explore parametrizations?

    # run metaproject ----------------------------------------------------------
    assert (
        RUN_PROJECT.request_desc
        == "POST /computation/pipeline/18f1938c-567d-11ec-b2f3-02420a000010:start"
    )
    resp = await client.request(
        RUN_PROJECT.method,
        RUN_PROJECT.path,
        json=RUN_PROJECT.request_payload,
    )
    assert resp.status
    body = await resp.json()
    assert RUN_PROJECT.response_body == body

    project_uuid = body["data"]["pipeline_id"]
    ref_ids = body["data"]["ref_ids"]

    # TODO: check: has auto-commited
    # TODO: check: has iterations as branches
    # TODO:retrieve results of iter1

    resp = await client.get(
        f"/v0/projects/{project_uuid}/checkpoint/HEAD/iterations?offset=0"
    )
    body = await resp.json()
    iterlist_a = Page[ProjectIterationAsItem].parse_obj(body).data

    assert len(iterlist_a) == 3

    resp = await client.get(iterlist_a[0].wcopy_project_url.path)
    assert resp.status == HTTPStatus.OK

    body = await resp.json()
    project_iter0 = body["data"]

    outputs = {}
    for nid, node in project_iter0["workbench"]:
        if out := node.get("outputs"):
            outputs[nid] = out

    # TODO: change iterations from 0:4 -> HEAD+1
    resp = await client.get(f"/v0/projects/{project_uuid}")
    body = await resp.json()

    project = Project.parse_obj(body["data"])
    new_project = project.copy(
        update={
            "workbench": {
                "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                    "inputs": {
                        "linspace_start": 0,
                        "linspace_stop": 4,
                        "linspace_step": 1,
                    }
                }
            }
        }
    )

    # create iterations
    resp = await client.post(f"/v0/projects/{project_uuid}/checkpoint/HEAD/iterations")
    assert resp.status == HTTPStatus.CREATED

    # check new auto-commit
    # check four new branches
    #

    # retrieve them
    resp = await client.get(
        f"/v0/projects/{project_uuid}/checkpoint/HEAD/iterations?offset=0"
    )
    body = await resp.json()
    iterlist_b = Page[ProjectIterationAsItem].parse_obj(body).data
    assert len(iterlist_b) == 4

    # run
    resp = await client.request(
        RUN_PROJECT.method,
        RUN_PROJECT.path,
        json=RUN_PROJECT.request_payload,
    )

    # TODO: checkout i


@pytest.mark.skip(reason="DEV")
def test_it1():

    respath = Path("/home/crespo/Downloads/response_1633600264408.json")
    csvpath = Path("/home/crespo/Downloads/projects.csv")

    reponse_body = json.loads(respath.read_text())

    project_api_dict = reponse_body["data"]

    with open("project_api_dict.json", "wt") as fh:
        print(json.dumps(project_api_dict, **JSON_KWARGS), file=fh)

    project_api_model = Project.parse_obj(project_api_dict)
    with open("project_api_model.json", "wt") as fh:
        print(
            project_api_model.json(by_alias=True, exclude_unset=True, **JSON_KWARGS),
            file=fh,
        )

    project_db_model = load_projects_exported_as_csv(csvpath, delimiter=";")[0]
    with open("project_db_model.json", "wt") as fh:
        print(
            project_db_model.json(by_alias=True, exclude_unset=True, **JSON_KWARGS),
            file=fh,
        )

    # given a api_project_model -> convert it into a db project model

    obj = project_api_model.dict(exclude_unset=True)
    obj["prj_owner"] = 3  # email -> int
    new_project_db_model = ProjectForPgInsert.parse_obj(obj)

    with open("new_project_db_model.json", "wt") as fh:
        print(
            new_project_db_model.to_values(**JSON_KWARGS),
            file=fh,
        )

    # obj.dict(exclude=)

    # elimitate excess
    # ProjectAtDB.Config.extra = Extra.allow

    # transform email -> id
    obj["prj_owner"] = 1

    # add in db but not in obj?
    # id is not required
    #

    # m = ProjectAtDB.parse_obj({  ,**api_project_model.dict()})

    # with open("db_project_model2.json", "wt") as fh:
    #     print(
    #         m.json(
    #             by_alias=True, exclude_unset=True, **JSON_KWARGS
    #         ),
    #         file=fh,
    #     )


@pytest.mark.skip(reason="DEV")
def test_it2():
    from pydantic import BaseModel, Json

    class S(BaseModel):
        json_obj: Union[Dict, Json]

    ss = S(json_obj='{"x": 3, "y": {"z": 2}}')
    print(ss.json_obj, type(ss.json_obj))

    ss = S(json_obj={"x": 3, "y": {"z": 2}})
    print(ss.json_obj, type(ss.json_obj))

    ss = S(json_obj="[1, 2, 3 ]")
    print(ss.json_obj, type(ss.json_obj))
    ss = S(json_obj=[1, 2, 3])
    print(ss.json_obj, type(ss.json_obj))

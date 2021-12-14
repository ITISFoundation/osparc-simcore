# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from http import HTTPStatus
from pathlib import Path
from typing import Dict, Union

import pytest
from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.database_project_models import (
    ProjectForPgInsert,
    load_projects_exported_as_csv,
)
from models_library.projects import Project
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import AUserDict
from pytest_simcore.simcore_webserver_projects_rest_api import (
    NEW_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    RUN_PROJECT,
)
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.models.projects import projects
from simcore_service_webserver.constants import APP_DB_ENGINE_KEY
from simcore_service_webserver.director_v2_api import get_project_run_policy
from simcore_service_webserver.meta_handlers import Page, ProjectIterationAsItem
from simcore_service_webserver.meta_projects import (
    meta_project_policy,
    projects_redirection_middleware,
)
from simcore_service_webserver.projects.project_models import ProjectDict

REQUEST_MODEL_POLICY = {
    "by_alias": True,
    "exclude_defaults": True,
    "exclude_none": True,  # e.g. thumbnail: None will fail validation
    "exclude_unset": True,
}

# FIXTURES ----------------------------------


@pytest.fixture
async def context_with_logged_user(client: TestClient, logged_user: AUserDict):

    yield

    engine = client.app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:

        # cascade deletes everything except projects_vc_snapshot
        await conn.execute(projects.delete())


# TESTS ----------------------------------


async def test_iterators_workflow(
    client: TestClient, context_with_logged_user: None, mocker, faker: Faker
):
    resp: ClientResponse

    # check init meta is correct
    assert projects_redirection_middleware in client.app.middlewares
    assert get_project_run_policy(client.app) == meta_project_policy

    # new project --------------------------------------------------------------
    mocker.patch(
        "simcore_service_webserver.director_v2_api.create_or_update_pipeline",
        return_value=None,
    )
    mocker.patch(
        "simcore_service_webserver.director_v2_api.get_computation_task",
        return_value=None,
    )
    # ----

    assert NEW_PROJECT.request_desc == "POST /v0/projects"
    resp = await client.post("/v0/projects", json=NEW_PROJECT.request_payload)
    assert resp.status == NEW_PROJECT.status_code, await resp.text()
    body = await resp.json()

    project_data: ProjectDict = body["data"]
    project_uuid = project_data["uuid"]

    # create meta-project: iterator 0:3 -> sleeper -> sleeper_2 ---------------
    modifications = REPLACE_PROJECT_ON_MODIFIED.request_payload
    assert modifications
    project_data.update({key: modifications[key] for key in ("workbench", "ui")})
    project_data["ui"].setdefault("currentNodeId", project_uuid)

    resp = await client.put(
        f"/v0/projects/{project_data['uuid']}",
        json=project_data,
    )
    assert resp.status == REPLACE_PROJECT_ON_MODIFIED.status_code, await resp.text()

    # TODO: create iterations, so user could explore parametrizations?

    # run metaproject ----------------------------------------------------------
    async def _mock_start(project_id, user_id, **options):
        return f"{project_id}"

    mocker.patch(
        "simcore_service_webserver.director_v2_core.DirectorV2ApiClient.start",
        side_effect=_mock_start,
    )
    # ----

    resp = await client.post(
        f"/v0/computation/pipeline/{project_uuid}:start",
        json=RUN_PROJECT.request_payload,
    )
    data, _ = await assert_status(resp, web.HTTPCreated)
    assert project_uuid == data["pipeline_id"]
    ref_ids = data["ref_ids"]
    assert len(ref_ids) == 3

    # TODO: check: has auto-commited
    # TODO: check: has iterations as branches
    # TODO:retrieve results of iter1

    # get iterations ----------------------------------------------------------
    resp = await client.get(f"/v0/repos/projects/{project_uuid}/checkpoints/HEAD")
    body = await resp.json()
    head_ref_id = body["data"]["id"]

    assert head_ref_id == 1

    resp = await client.get(
        f"/v0/projects/{project_uuid}/checkpoint/{head_ref_id}/iterations?offset=0"
    )
    body = await resp.json()
    first_iterlist = Page[ProjectIterationAsItem].parse_obj(body).data

    assert len(first_iterlist) == 3

    # get wcopy project for iter 0 ----------------------------------------------
    async def _mock_catalog_get(app, user_id, product_name, only_key_versions):
        return [
            {"key": s["key"], "version": s["version"]}
            for _, s in project_data["workbench"].items()
        ]

    mocker.patch(
        "simcore_service_webserver.catalog.get_services_for_user_in_product",
        side_effect=_mock_catalog_get,
    )

    # extract outputs
    for i, prj_iter in enumerate(first_iterlist):
        resp = await client.get(prj_iter.wcopy_project_url.path)
        assert resp.status == HTTPStatus.OK

        body = await resp.json()
        project_iter0 = body["data"]

        outputs = {}
        for nid, node in project_iter0["workbench"].items():
            if out := node.get("outputs"):
                outputs[nid] = out

        assert len(outputs) == 1
        assert outputs["fc9208d9-1a0a-430c-9951-9feaf1de3368"]["out_1"] == i

    # ----------------------------------------------

    # get project and modify iterator----------------------------------------------
    # TODO: change iterations from 0:4 -> HEAD+1
    resp = await client.get(f"/v0/projects/{project_uuid}")
    assert resp.status == HTTPStatus.OK, await resp.text()
    body = await resp.json()

    # TODO: updating a project fields can be daunting because
    # it combines nested field attributes with dicts and from the
    # json you cannot distinguish easily what-is-what automatically
    # Dict keys are usually some sort of identifier, typically a UUID or
    # and index but nothing prevents a dict from user other type of key types
    #
    project = Project.parse_obj(body["data"])
    new_project = project.copy(
        update={
            # FIXME: HACK to overcome export from None -> string
            # SOLUTION 1: thumbnail should not be required
            # SOLUTION 2: make thumbnail nullable
            "thumbnail": faker.image_url(),
        }
    )
    assert new_project.workbench is not None
    assert new_project.workbench
    node = new_project.workbench["fc9208d9-1a0a-430c-9951-9feaf1de3368"]
    assert node.inputs
    node.inputs["linspace_stop"] = 4

    resp = await client.put(
        f"/v0/projects/{project_uuid}",
        data=json_dumps(new_project.dict(**REQUEST_MODEL_POLICY)),
    )
    assert resp.status == HTTPStatus.OK, await resp.text()

    # create iterations ------------------------------------------------------------------
    if 0:
        # TODO: still not implemented
        resp = await client.post(
            f"/v0/projects/{project_uuid}/checkpoint/HEAD/iterations"
        )
        assert resp.status == HTTPStatus.NOT_IMPLEMENTED, await resp.text()

        # check new auto-commit
        # check four new branches
        #

        # retrieve iterations ---------------------------------------------------------------
        resp = await client.get(
            f"/v0/projects/{project_uuid}/checkpoint/HEAD/iterations?offset=0"
        )
        body = await resp.json()
        iterlist_b = Page[ProjectIterationAsItem].parse_obj(body).data
        assert len(iterlist_b) == 4

    # run them ---------------------------------------------------------------------------
    resp = await client.post(
        f"/v0/computation/pipeline/{project_uuid}:start",
        json=RUN_PROJECT.request_payload,
    )
    data, _ = await assert_status(resp, web.HTTPCreated)
    assert project_uuid == data["pipeline_id"]
    ref_ids = data["ref_ids"]
    assert len(ref_ids) == 4

    # get iterations -----------------------------------------------------------------
    # check iters 1, 2 and 3 share working copies
    #
    resp = await client.get(f"/v0/repos/projects/{project_uuid}/checkpoints/HEAD")
    body = await resp.json()
    head_ref_id = body["data"]["id"]

    assert head_ref_id == 5

    resp = await client.get(
        f"/v0/projects/{project_uuid}/checkpoint/{head_ref_id}/iterations?offset=0"
    )
    body = await resp.json()
    second_iterlist = Page[ProjectIterationAsItem].parse_obj(body).data

    assert len(second_iterlist) == 4
    assert len(set(it.wcopy_project_id for it in second_iterlist)) == len(
        second_iterlist
    ), "unique"

    for i in range(len(first_iterlist)):
        assert second_iterlist[i].wcopy_project_id == first_iterlist[i].wcopy_project_id

    # TODO: checkout i


@pytest.mark.skip(reason="DEV")
def test_it1():
    JSON_KWARGS = dict(indent=2, sort_keys=True)

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

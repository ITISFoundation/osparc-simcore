# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from http import HTTPStatus
from typing import Awaitable, Callable

import pytest
from aiohttp import ClientResponse, web
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects import Project
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_login import UserInfoDict
from pytest_simcore.simcore_webserver_projects_rest_api import (
    NEW_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    RUN_PROJECT,
)
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.models.projects import projects
from simcore_service_webserver._constants import APP_DB_ENGINE_KEY
from simcore_service_webserver.director_v2_api import get_project_run_policy
from simcore_service_webserver.meta_modeling_handlers import (
    Page,
    ProjectIterationItem,
    ProjectIterationResultItem,
)
from simcore_service_webserver.meta_modeling_projects import (
    meta_project_policy,
    projects_redirection_middleware,
)
from simcore_service_webserver.projects.project_models import ProjectDict

REQUEST_MODEL_POLICY = {
    "by_alias": True,
    "exclude_defaults": True,
    "exclude_none": True,  # e.g. thumbnail: None will fail validation TODO: remove when new project model is in place. It might lead to wrong errors
    "exclude_unset": True,
}


@pytest.fixture
async def context_with_logged_user(client: TestClient, logged_user: UserInfoDict):

    yield

    assert client.app
    engine = client.app[APP_DB_ENGINE_KEY]
    async with engine.acquire() as conn:
        # cascade deletes everything except projects_vc_snapshot
        await conn.execute(projects.delete())


@pytest.mark.acceptance_test
async def test_iterators_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    primary_group,
    context_with_logged_user: None,
    mocker,
    faker: Faker,
    director_v2_service_mock: None,
    request_create_project: Callable[..., Awaitable[ProjectDict]],
):
    # pylint: disable=too-many-statements

    #
    # NOTE: all TODOs below shall be addressed in next version of the iterator
    # SEE SEE https://github.com/ITISFoundation/osparc-simcore/issues/2735
    #

    resp: ClientResponse

    # check init meta is correct
    assert client.app
    assert projects_redirection_middleware in client.app.middlewares
    assert get_project_run_policy(client.app) == meta_project_policy

    # NEW project --------------------------------------------------------------
    mocker.patch(
        "simcore_service_webserver.director_v2_api.create_or_update_pipeline",
        return_value=None,
    )
    mocker.patch(
        "simcore_service_webserver.director_v2_api.get_computation_task",
        return_value=None,
    )
    # ----
    project_data = await request_create_project(
        client,
        web.HTTPAccepted,
        web.HTTPCreated,
        logged_user,
        primary_group,
        project=NEW_PROJECT.request_payload,
    )

    project_uuid = project_data["uuid"]

    # CREATE meta-project: iterator 0:3 -> sleeper -> sleeper_2 ---------------
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

    # RUN metaproject ----------------------------------------------------------
    async def _mock_start(project_id, user_id, product_name, **options):
        return f"{project_id}"

    mocker.patch(
        "simcore_service_webserver.director_v2_core_computations.ComputationsApi.start",
        side_effect=_mock_start,
    )
    # ----

    resp = await client.post(
        f"/v0/computations/{project_uuid}:start",
        json=RUN_PROJECT.request_payload,
    )
    data, _ = await assert_status(resp, web.HTTPCreated)
    assert project_uuid == data["pipeline_id"]
    ref_ids = data["ref_ids"]
    assert len(ref_ids) == 3

    # TODO: check: has auto-commited
    # TODO: check: has iterations as branches
    # TODO: retrieve results of iter1

    # GET iterations ----------------------------------------------------------
    resp = await client.get(f"/v0/repos/projects/{project_uuid}/checkpoints/HEAD")
    body = await resp.json()
    head_ref_id = body["data"]["id"]

    assert head_ref_id == 1

    resp = await client.get(
        f"/v0/projects/{project_uuid}/checkpoint/{head_ref_id}/iterations?offset=0"
    )
    body = await resp.json()
    first_iterlist = Page[ProjectIterationItem].parse_obj(body).data

    assert len(first_iterlist) == 3

    # GET workcopy project for iter 0 ----------------------------------------------
    async def _mock_catalog_get(app, user_id, product_name, only_key_versions):
        return [
            {"key": s["key"], "version": s["version"]}
            for _, s in project_data["workbench"].items()
        ] + [{"key": "simcore/services/frontend/parameter/integer", "version": "1.0.0"}]

    mocker.patch(
        "simcore_service_webserver.catalog.get_services_for_user_in_product",
        side_effect=_mock_catalog_get,
    )

    # extract outputs
    for i, prj_iter in enumerate(first_iterlist):
        resp = await client.get(prj_iter.workcopy_project_url.path)
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

    # GET results of all iterations
    # /projects/{project_uuid}/checkpoint/{ref_id}/iterations/-/results
    resp = await client.get(
        f"/v0/projects/{project_uuid}/checkpoint/{head_ref_id}/iterations/-/results"
    )
    assert resp.status == HTTPStatus.OK, await resp.text()
    body = await resp.json()

    results = Page[ProjectIterationResultItem].parse_obj(body).data

    # GET project and MODIFY iterator values----------------------------------------------
    #  - Change iterations from 0:4 -> HEAD+1
    resp = await client.get(f"/v0/projects/{project_uuid}")
    assert resp.status == HTTPStatus.OK, await resp.text()
    body = await resp.json()

    # NOTE: updating a project fields can be daunting because
    # it combines nested field attributes with dicts and from the
    # json you cannot distinguish easily what-is-what automatically
    # Dict keys are usually some sort of identifier, typically a UUID or
    # and index but nothing prevents a dict from using any other type of key types
    #
    project = Project.parse_obj(body["data"])
    new_project = project.copy(
        update={
            # TODO: HACK to overcome export from None -> string
            # SOLUTION 1: thumbnail should not be required (check with team!)
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

    # RUN again them ---------------------------------------------------------------------------
    resp = await client.post(
        f"/v0/computations/{project_uuid}:start",
        json=RUN_PROJECT.request_payload,
    )
    data, _ = await assert_status(resp, web.HTTPCreated)
    assert project_uuid == data["pipeline_id"]
    ref_ids = data["ref_ids"]
    assert len(ref_ids) == 4

    # GET iterations -----------------------------------------------------------------
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
    assert resp.status == HTTPStatus.OK, f"{body=}"  # nosec
    second_iterlist = Page[ProjectIterationItem].parse_obj(body).data

    assert len(second_iterlist) == 4
    assert len({it.workcopy_project_id for it in second_iterlist}) == len(
        second_iterlist
    ), "unique"

    # TODO: cached iterations will be implemented in next PR
    # for i in range(len(first_iterlist)):
    #    assert second_iterlist[i].workcopy_project_id == first_iterlist[i].workcopy_project_id

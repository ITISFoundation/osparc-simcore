# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


import pytest
from aiohttp import web
from pytest_simcore.helpers.utils_assert import assert_status
from pytest_simcore.helpers.utils_projects import assert_get_same_project
from simcore_service_webserver.db_models import UserRole


@pytest.mark.parametrize("user_role,expected", [(UserRole.USER, web.HTTPOk)])
async def test_tags_to_studies(
    client, logged_user, user_project, expected, test_tags_data, catalog_subsystem_mock
):
    catalog_subsystem_mock([user_project])
    # Add test tags
    tags = test_tags_data
    added_tags = []
    for tag in tags:
        url = client.app.router["create_tag"].url_for()
        resp = await client.post(url, json=tag)
        added_tag, _ = await assert_status(resp, expected)
        added_tags.append(added_tag)
        # Add tag to study
        url = client.app.router["add_tag"].url_for(
            project_uuid=user_project.get("uuid"), tag_id=str(added_tag.get("id"))
        )
        resp = await client.put(url)
        data, _ = await assert_status(resp, expected)
        # Tag is included in response
        assert added_tag.get("id") in data.get("tags")

    # check the tags are in
    user_project["tags"] = [tag["id"] for tag in added_tags]
    data = await assert_get_same_project(client, user_project, expected)

    # Delete tag0
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[0].get("id")))
    resp = await client.delete(url)
    await assert_status(resp, web.HTTPNoContent)
    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[0]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[0].get("id") not in data.get("tags")

    # Remove tag1 from project
    url = client.app.router["remove_tag"].url_for(
        project_uuid=user_project.get("uuid"), tag_id=str(added_tags[1].get("id"))
    )
    resp = await client.delete(url)
    await assert_status(resp, expected)
    # Get project and check that tag is no longer there
    user_project["tags"].remove(added_tags[1]["id"])
    data = await assert_get_same_project(client, user_project, expected)
    assert added_tags[1].get("id") not in data.get("tags")

    # Delete tag1
    url = client.app.router["delete_tag"].url_for(tag_id=str(added_tags[1].get("id")))
    resp = await client.delete(url)
    await assert_status(resp, web.HTTPNoContent)

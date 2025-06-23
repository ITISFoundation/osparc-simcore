# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-statements


from collections.abc import Callable
from http import HTTPStatus
from unittest.mock import MagicMock

import pytest
import simcore_service_webserver.conversations._conversation_message_service
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from models_library.api_schemas_webserver.projects_conversations import (
    ConversationMessageRestGet,
    ConversationRestGet,
)
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.webserver_login import LoggedUser, UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver._meta import api_version_prefix
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects._groups_repository import (
    update_or_insert_project_group,
)
from simcore_service_webserver.projects.models import ProjectDict

API_PREFIX = "/" + api_version_prefix


@pytest.fixture
def mock_notify_function(mocker: MockerFixture) -> Callable[[str], MagicMock]:
    def _mock(function_name: str) -> MagicMock:
        return mocker.patch.object(
            simcore_service_webserver.conversations._conversation_message_service,
            function_name,
        )

    return _mock


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_project_conversations_user_role_access(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    user_role: UserRole,
    expected: HTTPStatus,
):
    assert client.app
    base_url = client.app.router["list_project_conversations"].url_for(
        project_id=user_project["uuid"]
    )
    resp = await client.get(f"{base_url}")
    assert resp.status == 401 if user_role == UserRole.ANONYMOUS else 200


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/private-issues/issues/51"
)
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_project_conversations_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
):
    base_url = client.app.router["list_project_conversations"].url_for(
        project_id=user_project["uuid"]
    )
    resp = await client.get(f"{base_url}")
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert data == []
    assert meta["total"] == 0
    assert links

    # Now we will create first conversation
    body = {"name": "My conversation", "type": "PROJECT_STATIC"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationRestGet.model_validate(data)
    _first_conversation_id = data["conversationId"]

    # Now we will create second conversation
    body = {"name": "My conversation", "type": "PROJECT_ANNOTATION"}
    resp = await client.post(f"{base_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationRestGet.model_validate(data)

    # Now we will list all conversations for the project
    resp = await client.get(f"{base_url}")
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 2
    assert meta["total"] == 2
    assert links

    # Now we will update the first conversation
    updated_name = "Updated first conversation"
    resp = await client.put(
        f"{base_url}/{_first_conversation_id}",
        json={"name": updated_name},
    )
    data, _ = await assert_status(
        resp,
        expected,
    )
    # Now we will get the first conversation
    resp = await client.get(f"{base_url}/{_first_conversation_id}")
    data, _ = await assert_status(
        resp,
        expected,
    )
    assert data["name"] == updated_name

    # Now we will delete the first conversation
    resp = await client.delete(f"{base_url}/{_first_conversation_id}")
    data, _ = await assert_status(
        resp,
        status.HTTP_204_NO_CONTENT,
    )

    # Now we will list all conversations for the project
    resp = await client.get(f"{base_url}")
    data, _, meta = await assert_status(
        resp,
        expected,
        include_meta=True,
    )
    assert len(data) == 1
    assert meta["total"] == 1


@pytest.mark.acceptance_test(
    "https://github.com/ITISFoundation/private-issues/issues/51"
)
@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.USER, status.HTTP_200_OK),
    ],
)
async def test_project_conversation_messages_full_workflow(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    expected: HTTPStatus,
    postgres_db: sa.engine.Engine,
    mock_notify_function: Callable[[str], MagicMock],
):
    mocked_notify_conversation_message_created = mock_notify_function(
        "notify_conversation_message_created"
    )
    mocked_notify_conversation_message_updated = mock_notify_function(
        "notify_conversation_message_updated"
    )
    mocked_notify_conversation_message_deleted = mock_notify_function(
        "notify_conversation_message_deleted"
    )

    base_project_url = client.app.router["list_project_conversations"].url_for(
        project_id=user_project["uuid"]
    )
    # Now we will create conversation
    body = {"name": "My conversation", "type": "PROJECT_STATIC"}
    resp = await client.post(f"{base_project_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationRestGet.model_validate(data)
    _conversation_id = data["conversationId"]

    base_project_conversation_url = client.app.router[
        "list_project_conversation_messages"
    ].url_for(project_id=user_project["uuid"], conversation_id=_conversation_id)

    # Now we will add first message
    body = {"content": "My first message", "type": "MESSAGE"}
    resp = await client.post(f"{base_project_conversation_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationMessageRestGet.model_validate(data)
    _first_message_id = data["messageId"]

    assert mocked_notify_conversation_message_created.call_count == 1
    kwargs = mocked_notify_conversation_message_created.call_args.kwargs

    assert f"{kwargs['project_id']}" == user_project["uuid"]
    assert kwargs["conversation_message"].content == "My first message"

    # Now we will add second message
    body = {"content": "My second message", "type": "MESSAGE"}
    resp = await client.post(f"{base_project_conversation_url}", json=body)
    data, _ = await assert_status(
        resp,
        status.HTTP_201_CREATED,
    )
    assert ConversationMessageRestGet.model_validate(data)
    _second_message_id = data["messageId"]

    assert mocked_notify_conversation_message_created.call_count == 2
    kwargs = mocked_notify_conversation_message_created.call_args.kwargs

    assert user_project["uuid"] == f"{kwargs['project_id']}"
    assert kwargs["conversation_message"].content == "My second message"

    # Now we will list all message for the project conversation
    resp = await client.get(f"{base_project_conversation_url}")
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 2
    assert meta["total"] == 2
    assert links
    # NOTE: the order of the messages is important, should be ordered by created date descending
    assert data[0]["messageId"] == _second_message_id
    assert data[1]["messageId"] == _first_message_id

    # Now we will update the second message
    updated_content = "Updated second message"
    resp = await client.put(
        f"{base_project_conversation_url}/{_second_message_id}",
        json={"content": updated_content},
    )
    data, _ = await assert_status(
        resp,
        expected,
    )

    assert mocked_notify_conversation_message_updated.call_count == 1
    kwargs = mocked_notify_conversation_message_updated.call_args.kwargs

    assert user_project["uuid"] == f"{kwargs['project_id']}"
    assert kwargs["conversation_message"].content == updated_content

    # Get the second message
    resp = await client.get(f"{base_project_conversation_url}/{_second_message_id}")
    data, _ = await assert_status(
        resp,
        expected,
    )
    assert data["content"] == updated_content

    # Ordering should be still the same
    resp = await client.get(f"{base_project_conversation_url}")
    data, _, meta, links = await assert_status(
        resp,
        expected,
        include_meta=True,
        include_links=True,
    )
    assert len(data) == 2
    assert meta["total"] == 2
    assert links
    # NOTE: the order of the messages is important, should be ordered by created date descending
    assert data[0]["messageId"] == _second_message_id
    assert data[1]["messageId"] == _first_message_id

    # Now we will delete the second comment
    resp = await client.delete(f"{base_project_conversation_url}/{_second_message_id}")
    data, _ = await assert_status(
        resp,
        status.HTTP_204_NO_CONTENT,
    )

    assert mocked_notify_conversation_message_deleted.call_count == 1
    kwargs = mocked_notify_conversation_message_deleted.call_args.kwargs

    assert f"{kwargs['project_id']}" == user_project["uuid"]
    assert f"{kwargs['conversation_id']}" == _conversation_id
    assert f"{kwargs['message_id']}" == _second_message_id

    # Now we will list all message for the project conversation
    resp = await client.get(f"{base_project_conversation_url}")
    data, _, meta = await assert_status(resp, expected, include_meta=True)
    assert len(data) == 1
    assert meta["total"] == 1
    assert data[0]["messageId"] == _first_message_id

    # Now we will log as a different user
    async with LoggedUser(client) as new_logged_user:
        # As this user does not have access to the project, they should get 403
        resp = await client.get(f"{base_project_conversation_url}")
        _, errors = await assert_status(
            resp,
            status.HTTP_403_FORBIDDEN,
        )
        assert errors

        resp = await client.get(f"{base_project_conversation_url}/{_first_message_id}")
        _, errors = await assert_status(
            resp,
            status.HTTP_403_FORBIDDEN,
        )
        assert errors

        # Now we will share the project with the new user
        await update_or_insert_project_group(
            client.app,
            project_id=user_project["uuid"],
            group_id=new_logged_user["primary_gid"],
            read=True,
            write=True,
            delete=True,
        )

        # Now the user should have access to the project now
        # New user will add comment
        resp = await client.post(
            f"{base_project_conversation_url}",
            json={"content": "My first message as a new user", "type": "MESSAGE"},
        )
        data, _ = await assert_status(
            resp,
            status.HTTP_201_CREATED,
        )
        _new_user_message_id = data["messageId"]

        # New user will modify the comment
        updated_content = "Updated My first message as a new user"
        resp = await client.put(
            f"{base_project_conversation_url}/{_new_user_message_id}",
            json={"content": updated_content},
        )
        data, _ = await assert_status(
            resp,
            expected,
        )
        assert data["content"] == updated_content

        # New user will list all conversations
        resp = await client.get(f"{base_project_conversation_url}")
        data, _, meta, links = await assert_status(
            resp,
            expected,
            include_meta=True,
            include_links=True,
        )
        assert meta["total"] == 2
        assert links
        assert len(data) == 2

        # New user will modify message of the previous user
        updated_content = "Updated comment of previous user"
        resp = await client.put(
            f"{base_project_conversation_url}/{_first_message_id}",
            json={"content": updated_content},
        )
        data, _ = await assert_status(
            resp,
            expected,
        )
        assert data["content"] == updated_content

        # New user will delete comment of the previous user
        resp = await client.delete(
            f"{base_project_conversation_url}/{_first_message_id}"
        )
        data, _ = await assert_status(
            resp,
            status.HTTP_204_NO_CONTENT,
        )

        assert mocked_notify_conversation_message_deleted.call_count == 2
        kwargs = mocked_notify_conversation_message_deleted.call_args.kwargs

        assert f"{kwargs['project_id']}" == user_project["uuid"]
        assert f"{kwargs['conversation_id']}" == _conversation_id
        assert f"{kwargs['message_id']}" == _first_message_id

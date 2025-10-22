# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from http import HTTPStatus

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.api_schemas_webserver.users import (
    MyProfileRestGet,
)
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.monkeypatch_envs import EnvVarsDict, setenvs_from_dict
from pytest_simcore.helpers.webserver_users import UserInfoDict
from servicelib.aiohttp import status
from simcore_service_webserver.models import PhoneNumberStr
from simcore_service_webserver.users._controller.rest.profile_rest import (
    _REGISTRATION_CODE_VALUE_FAKE,
)


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict, monkeypatch: pytest.MonkeyPatch
) -> EnvVarsDict:
    # disables GC and DB-listener
    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_DEV_FEATURES_ENABLED": "1",  # NOTE: still under development
        },
    )


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_registration_basic_workflow(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    # GET initial profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    initial_profile = MyProfileRestGet.model_validate(data)
    initial_phone = initial_profile.phone
    assert initial_phone

    # REGISTER phone number
    # Change the last 3 digits of the initial phone number to '999'
    new_phone = f"{initial_phone[:-3]}999"
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    # CONFIRM phone registration
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": _REGISTRATION_CODE_VALUE_FAKE,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET updated profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    updated_profile = MyProfileRestGet.model_validate(data)

    # Verify phone was updated
    assert updated_profile.phone == new_phone
    assert updated_profile.phone != initial_phone

    # Verify other fields remained unchanged
    assert updated_profile.first_name == initial_profile.first_name
    assert updated_profile.last_name == initial_profile.last_name
    assert updated_profile.login == initial_profile.login
    assert updated_profile.user_name == initial_profile.user_name


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_registration_workflow(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    # GET initial profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    initial_profile = MyProfileRestGet.model_validate(data)
    initial_phone = initial_profile.phone
    assert initial_phone

    # STEP 1: REGISTER phone number
    new_phone = f"{initial_phone[:-3]}999"  # Change the last 3 digits to '999'
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    # STEP 2: CONFIRM phone registration
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": _REGISTRATION_CODE_VALUE_FAKE,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET updated profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    updated_profile = MyProfileRestGet.model_validate(data)

    # Verify phone was updated
    assert updated_profile.phone == new_phone
    assert updated_profile.phone != initial_phone

    # Verify other fields remained unchanged
    assert updated_profile.first_name == initial_profile.first_name
    assert updated_profile.last_name == initial_profile.last_name
    assert updated_profile.login == initial_profile.login
    assert updated_profile.user_name == initial_profile.user_name


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_registration_with_resend(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    user_phone_number: PhoneNumberStr,
):
    assert client.app

    # STEP 1: REGISTER phone number
    new_phone = user_phone_number
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    # STEP 2: RESEND code (optional step)
    url = client.app.router["my_phone_resend"].url_for()
    resp = await client.post(f"{url}")
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    # STEP 3: CONFIRM phone registration
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": _REGISTRATION_CODE_VALUE_FAKE,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET updated profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    updated_profile = MyProfileRestGet.model_validate(data)

    # Verify phone was updated
    assert updated_profile.phone == new_phone


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_registration_change_existing_phone(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    user_phone_number: PhoneNumberStr,
):
    assert client.app

    # Set initial phone
    first_phone = user_phone_number
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": first_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": _REGISTRATION_CODE_VALUE_FAKE,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # Change to new phone
    # Create a different phone number by changing the last digits
    new_phone = user_phone_number[:-4] + "9999"
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": _REGISTRATION_CODE_VALUE_FAKE,
        },
    )
    await assert_status(resp, status.HTTP_204_NO_CONTENT)

    # GET updated profile
    url = client.app.router["get_my_profile"].url_for()
    resp = await client.get(f"{url}")
    data, _ = await assert_status(resp, status.HTTP_200_OK)

    updated_profile = MyProfileRestGet.model_validate(data)

    # Verify phone was updated to new phone
    assert updated_profile.phone == new_phone
    assert updated_profile.phone != first_phone


#
# PHONE REGISTRATION FAILURE TESTS
#


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_resend_without_pending_registration(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    # Try to resend code without any pending registration
    url = client.app.router["my_phone_resend"].url_for()
    resp = await client.post(f"{url}")
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_confirm_without_pending_registration(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    # Try to confirm code without any pending registration
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": _REGISTRATION_CODE_VALUE_FAKE,
        },
    )
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_confirm_with_wrong_code(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    user_phone_number: PhoneNumberStr,
):
    assert client.app

    # STEP 1: REGISTER phone number
    new_phone = user_phone_number
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    # STEP 2: Try to confirm with wrong code
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": "wrongcode1234",
        },
    )
    await assert_status(resp, status.HTTP_400_BAD_REQUEST)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_confirm_with_invalid_code_format(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    user_phone_number: PhoneNumberStr,
):
    assert client.app

    # STEP 1: REGISTER phone number
    new_phone = user_phone_number
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    # STEP 2: Try to confirm with invalid code format (contains special characters)
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": "123-456",  # Invalid format according to pattern
        },
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_register_with_empty_phone(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
):
    assert client.app

    # Try to register with empty phone number
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": "",  # Empty phone number
        },
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)

    # Try to register with whitespace-only phone number
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": "   ",  # Whitespace only
        },
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_phone_confirm_with_empty_code(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    user_phone_number: PhoneNumberStr,
):
    assert client.app

    # STEP 1: REGISTER phone number
    new_phone = user_phone_number
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": new_phone,
        },
    )
    await assert_status(resp, status.HTTP_202_ACCEPTED)

    # STEP 2: Try to confirm with empty code
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": "",  # Empty code
        },
    )
    await assert_status(resp, status.HTTP_422_UNPROCESSABLE_ENTITY)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_phone_register_access_rights(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    expected: HTTPStatus,
    user_phone_number: PhoneNumberStr,
):
    assert client.app

    # Try to register phone with insufficient permissions
    url = client.app.router["my_phone_register"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "phone": user_phone_number,
        },
    )
    await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_phone_resend_access_rights(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    expected: HTTPStatus,
):
    assert client.app

    # Try to resend code with insufficient permissions
    url = client.app.router["my_phone_resend"].url_for()
    resp = await client.post(f"{url}")
    await assert_status(resp, expected)


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_403_FORBIDDEN),
    ],
)
async def test_phone_confirm_access_rights(
    user_role: UserRole,
    logged_user: UserInfoDict,
    client: TestClient,
    expected: HTTPStatus,
):
    assert client.app

    # Try to confirm code with insufficient permissions
    url = client.app.router["my_phone_confirm"].url_for()
    resp = await client.post(
        f"{url}",
        json={
            "code": _REGISTRATION_CODE_VALUE_FAKE,
        },
    )
    await assert_status(resp, expected)

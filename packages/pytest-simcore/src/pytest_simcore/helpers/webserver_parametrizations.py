from typing import NamedTuple
from unittest import mock

from servicelib.aiohttp import status
from servicelib.status_utils import get_code_display_name
from simcore_postgres_database.models.users import UserRole


class ExpectedResponse(NamedTuple):
    """
    Stores respons status to an API request in function of the user

    e.g. for a request that normally returns OK, a non-authorized user
    will have no access, therefore ExpectedResponse.ok = HTTPUnauthorized
    """

    ok: int
    created: int
    no_content: int
    not_found: int
    forbidden: int
    locked: int
    accepted: int
    unprocessable: int
    not_acceptable: int
    conflict: int

    def __str__(self) -> str:
        # pylint: disable=no-member
        items = ", ".join(
            f"{k}={get_code_display_name(c)}" for k, c in self._asdict().items()
        )
        return f"{self.__class__.__name__}({items})"


def standard_role_response() -> tuple[str, list[tuple[UserRole, ExpectedResponse]]]:
    return (
        "user_role,expected",
        [
            (
                UserRole.ANONYMOUS,
                ExpectedResponse(
                    ok=status.HTTP_401_UNAUTHORIZED,
                    created=status.HTTP_401_UNAUTHORIZED,
                    no_content=status.HTTP_401_UNAUTHORIZED,
                    not_found=status.HTTP_401_UNAUTHORIZED,
                    forbidden=status.HTTP_401_UNAUTHORIZED,
                    locked=status.HTTP_401_UNAUTHORIZED,
                    accepted=status.HTTP_401_UNAUTHORIZED,
                    unprocessable=status.HTTP_401_UNAUTHORIZED,
                    not_acceptable=status.HTTP_401_UNAUTHORIZED,
                    conflict=status.HTTP_401_UNAUTHORIZED,
                ),
            ),
            (
                UserRole.GUEST,
                ExpectedResponse(
                    ok=status.HTTP_403_FORBIDDEN,
                    created=status.HTTP_403_FORBIDDEN,
                    no_content=status.HTTP_403_FORBIDDEN,
                    not_found=status.HTTP_403_FORBIDDEN,
                    forbidden=status.HTTP_403_FORBIDDEN,
                    locked=status.HTTP_403_FORBIDDEN,
                    accepted=status.HTTP_403_FORBIDDEN,
                    unprocessable=status.HTTP_403_FORBIDDEN,
                    not_acceptable=status.HTTP_403_FORBIDDEN,
                    conflict=status.HTTP_403_FORBIDDEN,
                ),
            ),
            (
                UserRole.USER,
                ExpectedResponse(
                    ok=status.HTTP_200_OK,
                    created=status.HTTP_201_CREATED,
                    no_content=status.HTTP_204_NO_CONTENT,
                    not_found=status.HTTP_404_NOT_FOUND,
                    forbidden=status.HTTP_403_FORBIDDEN,
                    locked=status.HTTP_423_LOCKED,
                    accepted=status.HTTP_202_ACCEPTED,
                    unprocessable=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    not_acceptable=status.HTTP_406_NOT_ACCEPTABLE,
                    conflict=status.HTTP_409_CONFLICT,
                ),
            ),
            (
                UserRole.TESTER,
                ExpectedResponse(
                    ok=status.HTTP_200_OK,
                    created=status.HTTP_201_CREATED,
                    no_content=status.HTTP_204_NO_CONTENT,
                    not_found=status.HTTP_404_NOT_FOUND,
                    forbidden=status.HTTP_403_FORBIDDEN,
                    locked=status.HTTP_423_LOCKED,
                    accepted=status.HTTP_202_ACCEPTED,
                    unprocessable=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    not_acceptable=status.HTTP_406_NOT_ACCEPTABLE,
                    conflict=status.HTTP_409_CONFLICT,
                ),
            ),
        ],
    )


def standard_user_role_response() -> (
    tuple[str, list[tuple[UserRole, ExpectedResponse]]]
):
    all_roles = standard_role_response()
    return (
        all_roles[0],
        [
            (user_role, response)
            for user_role, response in all_roles[1]
            if user_role in [UserRole.USER]
        ],
    )


class MockedStorageSubsystem(NamedTuple):
    copy_data_folders_from_project: mock.MagicMock
    delete_project: mock.MagicMock
    delete_node: mock.MagicMock
    get_project_total_size_simcore_s3: mock.MagicMock

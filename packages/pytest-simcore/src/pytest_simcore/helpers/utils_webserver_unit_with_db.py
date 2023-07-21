from typing import NamedTuple
from unittest import mock

from aiohttp import web
from servicelib.aiohttp.web_exceptions_extension import HTTPLockedError
from simcore_postgres_database.models.users import UserRole


class ExpectedResponse(NamedTuple):
    """
    Stores respons status to an API request in function of the user

    e.g. for a request that normally returns OK, a non-authorized user
    will have no access, therefore ExpectedResponse.ok = HTTPUnauthorized
    """

    ok: type[web.HTTPUnauthorized] | type[web.HTTPForbidden] | type[web.HTTPOk]
    created: (
        type[web.HTTPUnauthorized] | type[web.HTTPForbidden] | type[web.HTTPCreated]
    )
    no_content: (
        type[web.HTTPUnauthorized] | type[web.HTTPForbidden] | type[web.HTTPNoContent]
    )
    not_found: (
        type[web.HTTPUnauthorized] | type[web.HTTPForbidden] | type[web.HTTPNotFound]
    )
    forbidden: (type[web.HTTPUnauthorized] | type[web.HTTPForbidden])
    locked: type[web.HTTPUnauthorized] | type[web.HTTPForbidden] | type[HTTPLockedError]
    accepted: (
        type[web.HTTPUnauthorized] | type[web.HTTPForbidden] | type[web.HTTPAccepted]
    )
    unprocessable: (
        type[web.HTTPUnauthorized]
        | type[web.HTTPForbidden]
        | type[web.HTTPUnprocessableEntity]
    )
    not_acceptable: (
        type[web.HTTPUnauthorized]
        | type[web.HTTPForbidden]
        | type[web.HTTPNotAcceptable]
    )
    conflict: (
        type[web.HTTPUnauthorized] | type[web.HTTPForbidden] | type[web.HTTPConflict]
    )

    def __str__(self) -> str:
        # pylint: disable=no-member
        items = ",".join(f"{k}={v.__name__}" for k, v in self._asdict().items())
        return f"{self.__class__.__name__}({items})"


def standard_role_response() -> tuple[str, list[tuple[UserRole, ExpectedResponse]]]:
    return (
        "user_role,expected",
        [
            (
                UserRole.ANONYMOUS,
                ExpectedResponse(
                    ok=web.HTTPUnauthorized,
                    created=web.HTTPUnauthorized,
                    no_content=web.HTTPUnauthorized,
                    not_found=web.HTTPUnauthorized,
                    forbidden=web.HTTPUnauthorized,
                    locked=web.HTTPUnauthorized,
                    accepted=web.HTTPUnauthorized,
                    unprocessable=web.HTTPUnauthorized,
                    not_acceptable=web.HTTPUnauthorized,
                    conflict=web.HTTPUnauthorized,
                ),
            ),
            (
                UserRole.GUEST,
                ExpectedResponse(
                    ok=web.HTTPForbidden,
                    created=web.HTTPForbidden,
                    no_content=web.HTTPForbidden,
                    not_found=web.HTTPForbidden,
                    forbidden=web.HTTPForbidden,
                    locked=web.HTTPForbidden,
                    accepted=web.HTTPForbidden,
                    unprocessable=web.HTTPForbidden,
                    not_acceptable=web.HTTPForbidden,
                    conflict=web.HTTPForbidden,
                ),
            ),
            (
                UserRole.USER,
                ExpectedResponse(
                    ok=web.HTTPOk,
                    created=web.HTTPCreated,
                    no_content=web.HTTPNoContent,
                    not_found=web.HTTPNotFound,
                    forbidden=web.HTTPForbidden,
                    locked=HTTPLockedError,
                    accepted=web.HTTPAccepted,
                    unprocessable=web.HTTPUnprocessableEntity,
                    not_acceptable=web.HTTPNotAcceptable,
                    conflict=web.HTTPConflict,
                ),
            ),
            (
                UserRole.TESTER,
                ExpectedResponse(
                    ok=web.HTTPOk,
                    created=web.HTTPCreated,
                    no_content=web.HTTPNoContent,
                    not_found=web.HTTPNotFound,
                    forbidden=web.HTTPForbidden,
                    locked=HTTPLockedError,
                    accepted=web.HTTPAccepted,
                    unprocessable=web.HTTPUnprocessableEntity,
                    not_acceptable=web.HTTPNotAcceptable,
                    conflict=web.HTTPConflict,
                ),
            ),
        ],
    )


class MockedStorageSubsystem(NamedTuple):
    copy_data_folders_from_project: mock.MagicMock
    delete_project: mock.MagicMock
    delete_node: mock.MagicMock
    get_project_total_size_simcore_s3: mock.MagicMock

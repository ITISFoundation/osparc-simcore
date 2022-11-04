from typing import NamedTuple, Union
from unittest import mock

from aiohttp import web
from servicelib.aiohttp.web_exceptions_extension import HTTPLocked
from simcore_service_webserver.security_roles import UserRole


class ExpectedResponse(NamedTuple):
    """
    Stores respons status to an API request in function of the user

    e.g. for a request that normally returns OK, a non-authorized user
    will have no access, therefore ExpectedResponse.ok = HTTPUnauthorized
    """

    ok: Union[type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[web.HTTPOk]]
    created: Union[
        type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[web.HTTPCreated]
    ]
    no_content: Union[
        type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[web.HTTPNoContent]
    ]
    not_found: Union[
        type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[web.HTTPNotFound]
    ]
    forbidden: Union[
        type[web.HTTPUnauthorized],
        type[web.HTTPForbidden],
    ]
    locked: Union[type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[HTTPLocked]]
    accepted: Union[
        type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[web.HTTPAccepted]
    ]
    unprocessable: Union[
        type[web.HTTPUnauthorized],
        type[web.HTTPForbidden],
        type[web.HTTPUnprocessableEntity],
    ]
    not_acceptable: Union[
        type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[web.HTTPNotAcceptable]
    ]
    conflict: Union[
        type[web.HTTPUnauthorized], type[web.HTTPForbidden], type[web.HTTPConflict]
    ]

    def __str__(self) -> str:
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
                    locked=HTTPLocked,
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
                    locked=HTTPLocked,
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

from typing import List, NamedTuple, Tuple, Type, Union
from unittest import mock

from aiohttp import web
from simcore_service_webserver.projects.projects_handlers import HTTPLocked
from simcore_service_webserver.security_roles import UserRole


class ExpectedResponse(NamedTuple):
    """
    Stores respons status to an API request in function of the user

    e.g. for a request that normally returns OK, a non-authorized user
    will have no access, therefore ExpectedResponse.ok = HTTPUnauthorized
    """

    ok: Union[Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPOk]]
    created: Union[
        Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPCreated]
    ]
    no_content: Union[
        Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPNoContent]
    ]
    not_found: Union[
        Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPNotFound]
    ]
    forbidden: Union[
        Type[web.HTTPUnauthorized],
        Type[web.HTTPForbidden],
    ]
    locked: Union[Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[HTTPLocked]]
    accepted: Union[
        Type[web.HTTPUnauthorized], Type[web.HTTPForbidden], Type[web.HTTPAccepted]
    ]

    def __str__(self) -> str:
        items = ",".join(f"{k}={v.__name__}" for k, v in self._asdict().items())
        return f"{self.__class__.__name__}({items})"


def standard_role_response() -> Tuple[str, List[Tuple[UserRole, ExpectedResponse]]]:
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
                ),
            ),
        ],
    )


class MockedStorageSubsystem(NamedTuple):
    copy_data_folders_from_project: mock.MagicMock
    delete_project: mock.MagicMock

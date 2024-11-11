# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Literal

import pytest


@dataclass
class HttpApiCallCapture:
    """
    Captures relevant information of a call to the http api
    """

    name: str
    description: str
    method: Literal["GET", "PUT", "POST", "PATCH", "DELETE"]
    path: str
    query: str | None = None
    request_payload: dict[str, Any] | None = None
    response_body: dict[str, Any] | None = None
    status_code: HTTPStatus = HTTPStatus.OK

    def __str__(self) -> str:
        return f"{self.description: self.request_desc}"

    @property
    def request_desc(self) -> str:
        return f"{self.method} {self.path}"


#
# These capture info on the request/reponse calls at the front-end
# during a real session in which a project was created, modified, run and closed.
# This data can be obtained using the  browser's developer tools
#


NEW_PROJECT = HttpApiCallCapture(
    name="NEW_PROJECT",
    description="Press 'New Project'",
    method="POST",
    path="/v0/projects",
    request_payload={
        "uuid": "",
        "name": "New Study",
        "description": "",
        "prjOwner": "",
        "accessRights": {},
        "creationDate": "2021-12-06T10:07:47.547Z",
        "lastChangeDate": "2021-12-06T10:07:47.547Z",
        "thumbnail": "",
        "workbench": {},
    },
    response_body={
        "data": {
            "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
            "name": "New Study",
            "description": "",
            "accessRights": {"2": {"read": True, "write": True, "delete": True}},
            "creationDate": "2021-12-06T10:13:03.100Z",
            "lastChangeDate": "2021-12-06T10:13:03.100Z",
            "thumbnail": "",
            "workbench": {},
            "prjOwner": "foo@bar.com",
            "tags": [],
            "state": {
                "locked": {"value": False, "status": "CLOSED"},
                "state": {"value": "NOT_STARTED"},
            },
            "dev": None,
            "workspace_id": None,
            "folder_id": None,
            "trashed_at": None,
        },
        "error": None,
    },
    status_code=HTTPStatus.CREATED,
)


GET_PROJECT = HttpApiCallCapture(
    name="GET_PROJECT",
    description="Received newly created project",
    method="GET",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010",
    request_payload=None,
    response_body={
        "data": {
            "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
            "name": "New Study",
            "description": "",
            "thumbnail": "",
            "prjOwner": "foo@bar.com",
            "creationDate": "2021-12-06T10:13:03.100Z",
            "lastChangeDate": "2021-12-06T10:13:03.100Z",
            "workbench": {},
            "workspaceId": 123,
            "folderId": 2,
            "trashedAt": "2021-12-06T10:13:18.100Z",
            "accessRights": {"2": {"read": True, "write": True, "delete": True}},
            "dev": {},
            "classifiers": [],
            "ui": {},
            "quality": {},
            "tags": [],
            "state": {
                "locked": {"value": False, "status": "CLOSED"},
                "state": {"value": "NOT_STARTED"},
            },
            "workspace_id": None,
            "folder_id": None,
            "trashed_at": None,
        }
    },
)


OPEN_PROJECT = HttpApiCallCapture(
    name="OPEN_PROJECT",
    description="Open newly created project, i.e. project becomes active and dy-services are started",
    method="POST",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010:open",
    request_payload=None,
    response_body={
        "data": {
            "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
            "name": "New Study",
            "description": "",
            "thumbnail": "",
            "prjOwner": "foo@bar.com",
            "creationDate": "2021-12-06T10:13:03.100Z",
            "lastChangeDate": "2021-12-06T10:13:03.100Z",
            "workbench": {},
            "accessRights": {"2": {"read": True, "write": True, "delete": True}},
            "dev": {},
            "classifiers": [],
            "ui": {},
            "quality": {},
            "tags": [],
            "state": {
                "locked": {
                    "value": True,
                    "owner": {
                        "user_id": 1,
                        "first_name": "crespo",
                        "last_name": "",
                    },
                    "status": "OPENED",
                },
                "state": {"value": "NOT_STARTED"},
            },
            "workspace_id": None,
            "folder_id": None,
            "trashed_at": None,
        }
    },
)


REPLACE_PROJECT = HttpApiCallCapture(
    name="REPLACE_PROJECT",
    description="Saving periodically the project after modification (autosave)",
    method="PUT",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010",
    request_payload={
        "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
        "name": "New Study",
        "description": "",
        "prjOwner": "foo@bar.com",
        "accessRights": {"2": {"read": True, "write": True, "delete": True}},
        "creationDate": "2021-12-06T10:13:03.100Z",
        "lastChangeDate": "2021-12-06T10:13:03.100Z",
        "thumbnail": "",
        "workbench": {},
        "ui": {
            "workbench": {},
            "slideshow": {},
            "currentNodeId": "18f1938c-567d-11ec-b2f3-02420a000010",
            "mode": "workbench",
        },
        "tags": [],
        "classifiers": [],
        "quality": {
            "enabled": True,
            "tsr_current": {
                "r01": {"level": 0, "references": ""},
                "r02": {"level": 0, "references": ""},
                "r03": {"level": 0, "references": ""},
                "r04": {"level": 0, "references": ""},
                "r05": {"level": 0, "references": ""},
                "r06": {"level": 0, "references": ""},
                "r07": {"level": 0, "references": ""},
                "r08": {"level": 0, "references": ""},
                "r09": {"level": 0, "references": ""},
                "r10": {"level": 0, "references": ""},
            },
            "tsr_target": {
                "r01": {"level": 4, "references": ""},
                "r02": {"level": 4, "references": ""},
                "r03": {"level": 4, "references": ""},
                "r04": {"level": 4, "references": ""},
                "r05": {"level": 4, "references": ""},
                "r06": {"level": 4, "references": ""},
                "r07": {"level": 4, "references": ""},
                "r08": {"level": 4, "references": ""},
                "r09": {"level": 4, "references": ""},
                "r10": {"level": 4, "references": ""},
            },
            "annotations": {
                "certificationStatus": "Uncertified",
                "certificationLink": "",
                "vandv": "",
                "limitations": "",
            },
        },
    },
    response_body={
        "data": {
            "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
            "name": "New Study",
            "description": "",
            "thumbnail": "",
            "prjOwner": "foo@bar.com",
            "creationDate": "2021-12-06T10:13:03.100Z",
            "lastChangeDate": "2021-12-06T10:13:07.347Z",
            "workbench": {},
            "accessRights": {"2": {"read": True, "write": True, "delete": True}},
            "dev": {},
            "classifiers": [],
            "ui": {
                "mode": "workbench",
                "slideshow": {},
                "workbench": {},
                "currentNodeId": "18f1938c-567d-11ec-b2f3-02420a000010",
            },
            "quality": {
                "enabled": True,
                "tsr_target": {
                    "r01": {"level": 4, "references": ""},
                    "r02": {"level": 4, "references": ""},
                    "r03": {"level": 4, "references": ""},
                    "r04": {"level": 4, "references": ""},
                    "r05": {"level": 4, "references": ""},
                    "r06": {"level": 4, "references": ""},
                    "r07": {"level": 4, "references": ""},
                    "r08": {"level": 4, "references": ""},
                    "r09": {"level": 4, "references": ""},
                    "r10": {"level": 4, "references": ""},
                },
                "annotations": {
                    "vandv": "",
                    "limitations": "",
                    "certificationLink": "",
                    "certificationStatus": "Uncertified",
                },
                "tsr_current": {
                    "r01": {"level": 0, "references": ""},
                    "r02": {"level": 0, "references": ""},
                    "r03": {"level": 0, "references": ""},
                    "r04": {"level": 0, "references": ""},
                    "r05": {"level": 0, "references": ""},
                    "r06": {"level": 0, "references": ""},
                    "r07": {"level": 0, "references": ""},
                    "r08": {"level": 0, "references": ""},
                    "r09": {"level": 0, "references": ""},
                    "r10": {"level": 0, "references": ""},
                },
            },
            "tags": [],
            "state": {
                "locked": {
                    "value": True,
                    "owner": {
                        "user_id": 1,
                        "first_name": "crespo",
                        "last_name": "",
                    },
                    "status": "OPENED",
                },
                "state": {"value": "NOT_STARTED"},
            },
            "workspace_id": None,
            "folder_id": None,
            "trashed_at": None,
        }
    },
)


REPLACE_PROJECT_ON_MODIFIED = HttpApiCallCapture(
    name="REPLACE_PROJECT_ON_MODIFIED",
    description="After the user adds an iterator 1:3 and two sleepers, the project is saved",
    method="PUT",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010",
    request_payload={
        "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
        "name": "New Study",
        "description": "",
        "prjOwner": "foo@bar.com",
        "accessRights": {"2": {"read": True, "write": True, "delete": True}},
        "creationDate": "2021-12-06T10:13:03.100Z",
        "lastChangeDate": "2021-12-06T10:25:04.369Z",
        "thumbnail": "",
        "workbench": {
            "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                "key": "simcore/services/frontend/data-iterator/int-range",
                "version": "1.0.0",
                "label": "Integer iterator",
                "inputs": {
                    "linspace_start": 0,
                    "linspace_stop": 3,
                    "linspace_step": 1,
                },
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
            },
            "87663253-cecb-40e8-8429-dd2cd875166e": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.0.2",
                "label": "sleeper",
                "inputs": {
                    "input_2": {
                        "nodeUuid": "fc9208d9-1a0a-430c-9951-9feaf1de3368",
                        "output": "out_1",
                    },
                    "input_3": False,
                },
                "inputNodes": ["fc9208d9-1a0a-430c-9951-9feaf1de3368"],
                "parent": None,
                "thumbnail": "",
            },
            "305e9552-06fd-48a5-b9bc-36a8563fed67": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.0.2",
                "label": "sleeper_2",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                        "output": "output_1",
                    },
                    "input_2": {
                        "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                        "output": "output_2",
                    },
                    "input_3": False,
                },
                "inputNodes": ["87663253-cecb-40e8-8429-dd2cd875166e"],
                "parent": None,
                "thumbnail": "",
            },
        },
        "ui": {
            "workbench": {
                "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                    "position": {"x": 48, "y": 42}
                },
                "87663253-cecb-40e8-8429-dd2cd875166e": {
                    "position": {"x": 306, "y": 66}
                },
                "305e9552-06fd-48a5-b9bc-36a8563fed67": {
                    "position": {"x": 570, "y": 119}
                },
            },
            "slideshow": {},
            "currentNodeId": "18f1938c-567d-11ec-b2f3-02420a000010",
            "mode": "workbench",
        },
        "tags": [],
        "classifiers": [],
        "quality": {
            "enabled": True,
            "tsr_target": {
                "r01": {"level": 4, "references": ""},
                "r02": {"level": 4, "references": ""},
                "r03": {"level": 4, "references": ""},
                "r04": {"level": 4, "references": ""},
                "r05": {"level": 4, "references": ""},
                "r06": {"level": 4, "references": ""},
                "r07": {"level": 4, "references": ""},
                "r08": {"level": 4, "references": ""},
                "r09": {"level": 4, "references": ""},
                "r10": {"level": 4, "references": ""},
            },
            "annotations": {
                "vandv": "",
                "limitations": "",
                "certificationLink": "",
                "certificationStatus": "Uncertified",
            },
            "tsr_current": {
                "r01": {"level": 0, "references": ""},
                "r02": {"level": 0, "references": ""},
                "r03": {"level": 0, "references": ""},
                "r04": {"level": 0, "references": ""},
                "r05": {"level": 0, "references": ""},
                "r06": {"level": 0, "references": ""},
                "r07": {"level": 0, "references": ""},
                "r08": {"level": 0, "references": ""},
                "r09": {"level": 0, "references": ""},
                "r10": {"level": 0, "references": ""},
            },
        },
    },
    response_body={
        "data": {
            "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
            "name": "New Study",
            "description": "",
            "thumbnail": "",
            "prjOwner": "foo@bar.com",
            "creationDate": "2021-12-06T10:13:03.100Z",
            "lastChangeDate": "2021-12-06T10:25:10.379Z",
            "workbench": {
                "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                    "key": "simcore/services/frontend/data-iterator/int-range",
                    "version": "1.0.0",
                    "label": "Integer iterator",
                    "inputs": {
                        "linspace_start": 0,
                        "linspace_stop": 3,
                        "linspace_step": 1,
                    },
                    "inputNodes": [],
                    "parent": None,
                    "thumbnail": "",
                },
                "87663253-cecb-40e8-8429-dd2cd875166e": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.0.2",
                    "label": "sleeper",
                    "inputs": {
                        "input_2": {
                            "nodeUuid": "fc9208d9-1a0a-430c-9951-9feaf1de3368",
                            "output": "out_1",
                        },
                        "input_3": False,
                    },
                    "inputNodes": ["fc9208d9-1a0a-430c-9951-9feaf1de3368"],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "305e9552-06fd-48a5-b9bc-36a8563fed67": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.0.2",
                    "label": "sleeper_2",
                    "inputs": {
                        "input_1": {
                            "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                            "output": "output_1",
                        },
                        "input_2": {
                            "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                            "output": "output_2",
                        },
                        "input_3": False,
                    },
                    "inputNodes": ["87663253-cecb-40e8-8429-dd2cd875166e"],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": ["87663253-cecb-40e8-8429-dd2cd875166e"],
                        "currentStatus": "NOT_STARTED",
                    },
                },
            },
            "accessRights": {"2": {"read": True, "write": True, "delete": True}},
            "dev": {},
            "workspace_id": None,
            "folder_id": None,
            "trashed_at": None,
            "classifiers": [],
            "ui": {
                "mode": "workbench",
                "slideshow": {},
                "workbench": {
                    "305e9552-06fd-48a5-b9bc-36a8563fed67": {
                        "position": {"x": 570, "y": 119}
                    },
                    "87663253-cecb-40e8-8429-dd2cd875166e": {
                        "position": {"x": 306, "y": 66}
                    },
                    "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                        "position": {"x": 48, "y": 42}
                    },
                },
                "currentNodeId": "18f1938c-567d-11ec-b2f3-02420a000010",
            },
            "quality": {
                "enabled": True,
                "tsr_target": {
                    "r01": {"level": 4, "references": ""},
                    "r02": {"level": 4, "references": ""},
                    "r03": {"level": 4, "references": ""},
                    "r04": {"level": 4, "references": ""},
                    "r05": {"level": 4, "references": ""},
                    "r06": {"level": 4, "references": ""},
                    "r07": {"level": 4, "references": ""},
                    "r08": {"level": 4, "references": ""},
                    "r09": {"level": 4, "references": ""},
                    "r10": {"level": 4, "references": ""},
                },
                "annotations": {
                    "vandv": "",
                    "limitations": "",
                    "certificationLink": "",
                    "certificationStatus": "Uncertified",
                },
                "tsr_current": {
                    "r01": {"level": 0, "references": ""},
                    "r02": {"level": 0, "references": ""},
                    "r03": {"level": 0, "references": ""},
                    "r04": {"level": 0, "references": ""},
                    "r05": {"level": 0, "references": ""},
                    "r06": {"level": 0, "references": ""},
                    "r07": {"level": 0, "references": ""},
                    "r08": {"level": 0, "references": ""},
                    "r09": {"level": 0, "references": ""},
                    "r10": {"level": 0, "references": ""},
                },
            },
            "tags": [],
            "state": {
                "locked": {
                    "value": True,
                    "owner": {
                        "user_id": 1,
                        "first_name": "crespo",
                        "last_name": "",
                    },
                    "status": "OPENED",
                },
                "state": {"value": "NOT_STARTED"},
            },
        }
    },
)


RUN_PROJECT = HttpApiCallCapture(
    name="RUN_PROJECT",
    description="User press run button",
    method="POST",
    path="/computations/18f1938c-567d-11ec-b2f3-02420a000010:start",
    request_payload={"subgraph": [], "force_restart": False},
    response_body={
        "data": {
            "pipeline_id": "18f1938c-567d-11ec-b2f3-02420a000010",
            "ref_ids": [4, 5, 6],
        }
    },
    status_code=HTTPStatus.CREATED,
)


CLOSE_PROJECT = HttpApiCallCapture(
    name="CLOSE_PROJECT",
    description="Back to the dashboard, project closes",
    method="POST",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010:close",
    # FIXME: string as payload? should use proper json with 'client_session_id'
    request_payload="367885c0-324c-451c-85a5-b361d1feecb9",
    response_body=None,
    status_code=HTTPStatus.NO_CONTENT,
)


LIST_PROJECTS = HttpApiCallCapture(
    name="LIST_PROJECTS",
    description="Open browser in ashboard and user gets all projects",
    method="POST",
    path="/v0/projects?type=user&offset=0&limit=10",
    request_payload=None,
    response_body={
        "_meta": {"limit": 10, "total": 1, "offset": 0, "count": 1},
        "_links": {
            "self": "http://127.0.0.1.nip.io:9081/v0/projects?type=user&offset=0&limit=10",
            "first": "http://127.0.0.1.nip.io:9081/v0/projects?type=user&offset=0&limit=10",
            "prev": None,
            "next": None,
            "last": "http://127.0.0.1.nip.io:9081/v0/projects?type=user&offset=0&limit=10",
        },
        "data": [
            {
                "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
                "name": "New Study",
                "description": "",
                "thumbnail": "",
                "prjOwner": "foo@bar.com",
                "creationDate": "2021-12-06T10:13:03.100Z",
                "lastChangeDate": "2021-12-06T16:12:06.286Z",
                "accessRights": {"2": {"read": True, "write": True, "delete": True}},
                "workbench": {
                    "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                        "key": "simcore/services/frontend/data-iterator/int-range",
                        "version": "1.0.0",
                        "label": "Integer iterator",
                        "inputs": {
                            "linspace_start": 0,
                            "linspace_stop": 3,
                            "linspace_step": 1,
                        },
                        "inputNodes": [],
                        "parent": None,
                        "thumbnail": "",
                    },
                    "87663253-cecb-40e8-8429-dd2cd875166e": {
                        "key": "simcore/services/comp/itis/sleeper",
                        "version": "2.0.2",
                        "label": "sleeper",
                        "inputs": {
                            "input_2": {
                                "nodeUuid": "fc9208d9-1a0a-430c-9951-9feaf1de3368",
                                "output": "out_1",
                            },
                            "input_3": False,
                        },
                        "inputNodes": ["fc9208d9-1a0a-430c-9951-9feaf1de3368"],
                        "parent": None,
                        "thumbnail": "",
                        "state": {
                            "modified": True,
                            "dependencies": [],
                            "currentStatus": "NOT_STARTED",
                        },
                    },
                    "305e9552-06fd-48a5-b9bc-36a8563fed67": {
                        "key": "simcore/services/comp/itis/sleeper",
                        "version": "2.0.2",
                        "label": "sleeper_2",
                        "inputs": {
                            "input_1": {
                                "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                                "output": "output_1",
                            },
                            "input_2": {
                                "nodeUuid": "87663253-cecb-40e8-8429-dd2cd875166e",
                                "output": "output_2",
                            },
                            "input_3": False,
                        },
                        "inputNodes": ["87663253-cecb-40e8-8429-dd2cd875166e"],
                        "parent": None,
                        "thumbnail": "",
                        "state": {
                            "modified": True,
                            "dependencies": ["87663253-cecb-40e8-8429-dd2cd875166e"],
                            "currentStatus": "NOT_STARTED",
                        },
                    },
                },
                "ui": {
                    "mode": "workbench",
                    "slideshow": {},
                    "workbench": {
                        "305e9552-06fd-48a5-b9bc-36a8563fed67": {
                            "position": {"x": 570, "y": 119}
                        },
                        "87663253-cecb-40e8-8429-dd2cd875166e": {
                            "position": {"x": 306, "y": 66}
                        },
                        "fc9208d9-1a0a-430c-9951-9feaf1de3368": {
                            "position": {"x": 48, "y": 42}
                        },
                    },
                    "currentNodeId": "18f1938c-567d-11ec-b2f3-02420a000010",
                },
                "classifiers": [],
                "dev": {},
                "workspace_id": None,
                "folder_id": None,
                "trashed_at": None,
                "quality": {
                    "enabled": True,
                    "tsr_target": {
                        "r01": {"level": 4, "references": ""},
                        "r02": {"level": 4, "references": ""},
                        "r03": {"level": 4, "references": ""},
                        "r04": {"level": 4, "references": ""},
                        "r05": {"level": 4, "references": ""},
                        "r06": {"level": 4, "references": ""},
                        "r07": {"level": 4, "references": ""},
                        "r08": {"level": 4, "references": ""},
                        "r09": {"level": 4, "references": ""},
                        "r10": {"level": 4, "references": ""},
                    },
                    "annotations": {
                        "vandv": "",
                        "limitations": "",
                        "certificationLink": "",
                        "certificationStatus": "Uncertified",
                    },
                    "tsr_current": {
                        "r01": {"level": 0, "references": ""},
                        "r02": {"level": 0, "references": ""},
                        "r03": {"level": 0, "references": ""},
                        "r04": {"level": 0, "references": ""},
                        "r05": {"level": 0, "references": ""},
                        "r06": {"level": 0, "references": ""},
                        "r07": {"level": 0, "references": ""},
                        "r08": {"level": 0, "references": ""},
                        "r09": {"level": 0, "references": ""},
                        "r10": {"level": 0, "references": ""},
                    },
                },
                "tags": [],
                "state": {
                    "locked": {"value": False, "status": "CLOSED"},
                    "state": {"value": "NOT_STARTED"},
                },
            }
        ],
    },
)


SESSION_WORKFLOW = (
    NEW_PROJECT,
    GET_PROJECT,
    OPEN_PROJECT,
    REPLACE_PROJECT,
    REPLACE_PROJECT_ON_MODIFIED,
    RUN_PROJECT,
    CLOSE_PROJECT,
    LIST_PROJECTS,
)


CREATE_FROM_TEMPLATE = HttpApiCallCapture(
    name="CREATE_FROM_TEMPLATE",
    description="Click 'Sleeper study' card in Templates tab",
    method="POST",
    path="/v0/projects",
    query="from_study=ee87ff60-4147-4381-bcb8-59d076dbc788",
    request_payload={
        "uuid": "",
        "name": "Sleepers",
        "description": "5 sleepers interconnected",
        "prjOwner": "",
        "accessRights": {},
        "creationDate": "2023-04-13T10:12:13.197Z",
        "lastChangeDate": "2023-04-13T10:12:13.197Z",
        "thumbnail": "https://raw.githubusercontent.com/ITISFoundation/osparc-assets/main/assets/TheSoftWatches.jpg",
        "workbench": {},
    },
    response_body={
        "data": {
            "task_id": "POST%20%2Fv0%2Fprojects%3Ffrom_study%3Dee87ff60-4147-4381-bcb8-59d076dbc788.261e4470-4132-47a3-82d1-7c38bed30e13",
            "task_name": "POST /v0/projects?from_study=ee87ff60-4147-4381-bcb8-59d076dbc788",
            "status_href": "/v0/tasks/POST%2520%252Fv0%252Fprojects%253Ffrom_study%253Dee87ff60-4147-4381-bcb8-59d076dbc788.261e4470-4132-47a3-82d1-7c38bed30e13",
            "result_href": "/v0/tasks/POST%2520%252Fv0%252Fprojects%253Ffrom_study%253Dee87ff60-4147-4381-bcb8-59d076dbc788.261e4470-4132-47a3-82d1-7c38bed30e13/result",
            "abort_href": "/v0/tasks/POST%2520%252Fv0%252Fprojects%253Ffrom_study%253Dee87ff60-4147-4381-bcb8-59d076dbc788.261e4470-4132-47a3-82d1-7c38bed30e13",
        }
    },
    status_code=HTTPStatus.ACCEPTED,  # 202
)


CREATE_FROM_TEMPLATE__TASK_STATUS = HttpApiCallCapture(
    name="CREATE_FROM_TEMPLATE__TASK_STATUS",
    description="status_href that follows from CREATE_FROM_TEMPLATE",
    method="GET",
    path="/v0/tasks/POST%20%2Fv0%2Fprojects%3Ffrom_study%3Dee87ff60-4147-4381-bcb8-59d076dbc788.261e4470-4132-47a3-82d1-7c38bed30e13",
    response_body={
        "data": {
            "task_progress": {"message": "creating new study...", "percent": 0.0},
            "done": False,
            "started": "2023-04-13T10:16:45.602233",
        }
    },
    status_code=HTTPStatus.OK,  # 200
)


CREATE_FROM_TEMPLATE__TASK_RESULT = HttpApiCallCapture(
    name="CREATE_FROM_TEMPLATE__TASK_RESULT",
    description="status_href that follows from CREATE_FROM_TEMPLATE",
    method="GET",
    path="/v0/tasks/POST%2520%252Fv0%252Fprojects%253Ffrom_study%253Dee87ff60-4147-4381-bcb8-59d076dbc788.261e4470-4132-47a3-82d1-7c38bed30e13/result",
    response_body={
        "data": {
            "uuid": "4c58409a-d9e4-11ed-9c9e-02420a0b755a",
            "name": "Sleepers",
            "description": "5 sleepers interconnected",
            "thumbnail": "https://raw.githubusercontent.com/ITISFoundation/osparc-assets/main/assets/TheSoftWatches.jpg",
            "creationDate": "2023-04-13T10:16:47.521Z",
            "lastChangeDate": "2023-04-13T10:16:48.572Z",
            "accessRights": {"4": {"read": True, "write": True, "delete": True}},
            "workbench": {
                "f67a6277-b47f-5a17-9782-b9a92600e8c9": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "1.0.0",
                    "label": "sleeper 0",
                    "inputs": {"in_2": 2},
                    "inputAccess": {"in_1": "Invisible", "in_2": "ReadOnly"},
                    "inputNodes": [],
                    "outputNode": False,
                    "outputs": {},
                    "progress": 0,
                    "thumbnail": "",
                    "position": {"x": 50, "y": 300},
                    "state": {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "c898ccef-8ac9-5346-8e8b-99546c551d79": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "1.0.0",
                    "label": "sleeper 1",
                    "inputs": {
                        "in_1": {
                            "nodeUuid": "f67a6277-b47f-5a17-9782-b9a92600e8c9",
                            "output": "out_1",
                        },
                        "in_2": 2,
                    },
                    "inputNodes": ["f67a6277-b47f-5a17-9782-b9a92600e8c9"],
                    "outputNode": False,
                    "outputs": {},
                    "progress": 0,
                    "thumbnail": "",
                    "position": {"x": 300, "y": 200},
                    "state": {
                        "modified": True,
                        "dependencies": ["f67a6277-b47f-5a17-9782-b9a92600e8c9"],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "52a6c113-0615-55cd-b32f-5a8ead710562": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "1.0.0",
                    "label": "sleeper 2",
                    "inputs": {
                        "in_1": {
                            "nodeUuid": "c898ccef-8ac9-5346-8e8b-99546c551d79",
                            "output": "out_1",
                        },
                        "in_2": {
                            "nodeUuid": "c898ccef-8ac9-5346-8e8b-99546c551d79",
                            "output": "out_2",
                        },
                    },
                    "inputNodes": ["c898ccef-8ac9-5346-8e8b-99546c551d79"],
                    "outputNode": False,
                    "outputs": {},
                    "progress": 0,
                    "thumbnail": "",
                    "position": {"x": 550, "y": 200},
                    "state": {
                        "modified": True,
                        "dependencies": ["c898ccef-8ac9-5346-8e8b-99546c551d79"],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "1a93a810-749f-58c4-9506-0be716268427": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "1.0.0",
                    "label": "sleeper 3",
                    "inputs": {
                        "in_2": {
                            "nodeUuid": "f67a6277-b47f-5a17-9782-b9a92600e8c9",
                            "output": "out_2",
                        }
                    },
                    "inputNodes": ["f67a6277-b47f-5a17-9782-b9a92600e8c9"],
                    "outputNode": False,
                    "outputs": {},
                    "progress": 0,
                    "thumbnail": "",
                    "position": {"x": 420, "y": 400},
                    "state": {
                        "modified": True,
                        "dependencies": ["f67a6277-b47f-5a17-9782-b9a92600e8c9"],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "281f7845-f7ee-57a7-9b66-81931a30b254": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "1.0.0",
                    "label": "sleeper 4",
                    "inputs": {
                        "in_1": {
                            "nodeUuid": "52a6c113-0615-55cd-b32f-5a8ead710562",
                            "output": "out_1",
                        },
                        "in_2": {
                            "nodeUuid": "1a93a810-749f-58c4-9506-0be716268427",
                            "output": "out_2",
                        },
                    },
                    "inputNodes": [
                        "52a6c113-0615-55cd-b32f-5a8ead710562",
                        "1a93a810-749f-58c4-9506-0be716268427",
                    ],
                    "outputNode": False,
                    "outputs": {},
                    "progress": 0,
                    "thumbnail": "",
                    "position": {"x": 800, "y": 300},
                    "state": {
                        "modified": True,
                        "dependencies": [
                            "1a93a810-749f-58c4-9506-0be716268427",
                            "52a6c113-0615-55cd-b32f-5a8ead710562",
                        ],
                        "currentStatus": "NOT_STARTED",
                    },
                },
            },
            "ui": {
                "mode": "workbench",
                "slideshow": {},
                "workbench": {},
                "currentNodeId": "",
            },
            "classifiers": [],
            "dev": {},
            "workspace_id": None,
            "folder_id": None,
            "trashed_at": None,
            "quality": {
                "enabled": True,
                "tsr_target": {
                    "r01": {"level": 4, "references": ""},
                    "r02": {"level": 4, "references": ""},
                    "r03": {"level": 4, "references": ""},
                    "r04": {"level": 4, "references": ""},
                    "r05": {"level": 4, "references": ""},
                    "r06": {"level": 4, "references": ""},
                    "r07": {"level": 4, "references": ""},
                    "r08": {"level": 4, "references": ""},
                    "r09": {"level": 4, "references": ""},
                    "r10": {"level": 4, "references": ""},
                },
                "annotations": {
                    "vandv": "",
                    "limitations": "",
                    "certificationLink": "",
                    "certificationStatus": "Uncertified",
                },
                "tsr_current": {
                    "r01": {"level": 0, "references": ""},
                    "r02": {"level": 0, "references": ""},
                    "r03": {"level": 0, "references": ""},
                    "r04": {"level": 0, "references": ""},
                    "r05": {"level": 0, "references": ""},
                    "r06": {"level": 0, "references": ""},
                    "r07": {"level": 0, "references": ""},
                    "r08": {"level": 0, "references": ""},
                    "r09": {"level": 0, "references": ""},
                    "r10": {"level": 0, "references": ""},
                },
            },
            "prjOwner": "user@company.com",
            "tags": [22],
            "state": {
                "locked": {"value": False, "status": "CLOSED"},
                "state": {"value": "NOT_STARTED"},
            },
        }
    },
    status_code=HTTPStatus.CREATED,  # 201
)

DELETE_PROJECT = HttpApiCallCapture(
    name="DELETE_PROJECT",
    description="Deletes a given study",
    method="DELETE",
    path="/v0/projects/4c58409a-d9e4-11ed-9c9e-02420a0b755a",
    status_code=HTTPStatus.NO_CONTENT,  # 204
)


CREATE_FROM_SERVICE = HttpApiCallCapture(
    name="CREATE_FROM_SERVICE",
    description="Click 'Sleeper service' card in Services tab",
    method="POST",
    path="/v0/projects",
    request_payload={
        "uuid": "",
        "name": "sleeper",
        "description": "",
        "prjOwner": "",
        "accessRights": {},
        "creationDate": "2023-04-12T17:47:22.551Z",
        "lastChangeDate": "2023-04-12T17:47:22.551Z",
        "thumbnail": "https://raw.githubusercontent.com/ITISFoundation/osparc-assets/main/assets/TheSoftWatches.jpg",
        "workbench": {
            "5ecf6ef9-7600-4ac2-abe5-c3a2cc714e32": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.1.4",
                "label": "sleeper",
            }
        },
        "ui": {
            "workbench": {
                "5ecf6ef9-7600-4ac2-abe5-c3a2cc714e32": {
                    "position": {"x": 250, "y": 100}
                }
            }
        },
    },
    response_body={
        "data": {
            "task_id": "POST%20%2Fv0%2Fprojects.c81eb383-d5b7-4284-be34-36477530ac2e",
            "task_name": "POST /v0/projects",
            "status_href": "/v0/tasks/POST%2520%252Fv0%252Fprojects.c81eb383-d5b7-4284-be34-36477530ac2e",
            "result_href": "/v0/tasks/POST%2520%252Fv0%252Fprojects.c81eb383-d5b7-4284-be34-36477530ac2e/result",
            "abort_href": "/v0/tasks/POST%2520%252Fv0%252Fprojects.c81eb383-d5b7-4284-be34-36477530ac2e",
        }
    },
    status_code=HTTPStatus.ACCEPTED,  # 202
)


@pytest.fixture
def project_workflow_captures() -> tuple[HttpApiCallCapture, ...]:
    return tuple(deepcopy(c) for c in SESSION_WORKFLOW)

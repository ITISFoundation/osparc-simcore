# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Dict, Literal, Optional, Tuple

import pytest

# HELPERS ----------------------


@dataclass
class HttpApiCallCapture:
    """
    Captures relevant information of a call to the http api
    """

    description: str
    method: Literal["GET", "PUT", "POST", "PATCH"]
    path: str
    request_payload: Optional[Dict[str, Any]]
    response_body: Optional[Dict[str, Any]]
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
            "prjOwner": "crespo@itis.swiss",
            "tags": [],
            "state": {
                "locked": {"value": False, "status": "CLOSED"},
                "state": {"value": "NOT_STARTED"},
            },
        },
        "error": None,
    },
    status_code=HTTPStatus.CREATED,
)


GET_PROJECT = HttpApiCallCapture(
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
            "prjOwner": "crespo@itis.swiss",
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
                "locked": {"value": False, "status": "CLOSED"},
                "state": {"value": "NOT_STARTED"},
            },
        }
    },
)


OPEN_PROJECT = HttpApiCallCapture(
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
            "prjOwner": "crespo@itis.swiss",
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
        }
    },
)


REPLACE_PROJECT = HttpApiCallCapture(
    description="Saving periodically the project after modification (autosave)",
    method="PUT",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010",
    request_payload={
        "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
        "name": "New Study",
        "description": "",
        "prjOwner": "crespo@itis.swiss",
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
            "prjOwner": "crespo@itis.swiss",
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
        }
    },
)


REPLACE_PROJECT_ON_MODIFIED = HttpApiCallCapture(
    description="After the user adds an iterator 1:3 and two sleepers, the project is saved",
    method="PUT",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010",
    request_payload={
        "uuid": "18f1938c-567d-11ec-b2f3-02420a000010",
        "name": "New Study",
        "description": "",
        "prjOwner": "crespo@itis.swiss",
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
            "prjOwner": "crespo@itis.swiss",
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
    description="User press run button",
    method="POST",
    path="/computation/pipeline/18f1938c-567d-11ec-b2f3-02420a000010:start",
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
    description="Back to the dashboard, project closes",
    method="POST",
    path="/v0/projects/18f1938c-567d-11ec-b2f3-02420a000010:close",
    # FIXME: string as payload? should use proper json with 'client_session_id'
    request_payload="367885c0-324c-451c-85a5-b361d1feecb9",
    response_body=None,
    status_code=HTTPStatus.NO_CONTENT,
)


LIST_PROJECTS = HttpApiCallCapture(
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
                "prjOwner": "crespo@itis.swiss",
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


# FIXTURES ----------------------


@pytest.fixture
def project_workflow_captures() -> Tuple[HttpApiCallCapture, ...]:
    return tuple(deepcopy(c) for c in SESSION_WORKFLOW)

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

#
# These tests were build following requests/reponse calls from the front-end
# i.e. it captures models created by the front-end and response models by the backend
#


from pydantic import BaseModel, create_model
from simcore_service_webserver.projects._project_models_rest import SimcoreProject

# TODO: how could we implement all the model variants provided SimcoreProject as base???
#
# https://github.com/samuelcolvin/pydantic/issues/830#issuecomment-534141136
#
# 1. Use create_model to create your models "dynamically" (even if you actually do it un-dynamically)
# 2. Make the extra fields optional so they can be ignored.
#
# but there is a new __exclude_fields__ feature coming with https://github.com/samuelcolvin/pydantic/pull/2231


ProjectInNew = create_model(
    "PorjectInNew",
    **{
        name: field
        for name, field in SimcoreProject.__fields__.items()
        if name
        in {
            "name",
            "description",
            "thumbnail",
            "prj_owner",
            "access_rights",
        }
    }
)


# class ProjectInNew(BaseModel):
#    pass

# name:
# description:
# thumbnail:
# prj_owner:
# access_rights:


#    name: SimcoreProject.__fields__[]


class ProjectAsBody(SimcoreProject):
    pass


def test_create_new_empty_request_model():

    # POST /projects
    request_payload = {
        "uuid": "",
        "name": "New Study",
        "description": "",
        "prjOwner": "",
        "accessRights": {},
        "creationDate": "2021-12-02T08:57:32.449Z",
        "lastChangeDate": "2021-12-02T08:57:32.449Z",
        "thumbnail": "",
        "workbench": {},
    }
    project_in_new = ProjectAsBody.parse_obj(request_payload)


def test_create_new_empty_response_model():

    reponse_body = {
        "data": {
            "uuid": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
            "name": "New Study",
            "description": "",
            "accessRights": {"103": {"read": True, "write": True, "delete": True}},
            "creationDate": "2021-12-02T08:57:53.627Z",
            "lastChangeDate": "2021-12-02T08:57:53.627Z",
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
    }
    project_as_body = ProjectAsBody.parse_obj(reponse_body["data"])


def test_replace_opened_project_request_model():

    # PUT projects/ef6fa0a8-534d-11ec-89f5-02420a0fd439
    request_payload = {
        "uuid": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
        "name": "New Study",
        "description": "",
        "prjOwner": "crespo@itis.swiss",
        "accessRights": {"103": {"read": True, "write": True, "delete": True}},
        "creationDate": "2021-12-02T08:57:53.627Z",
        "lastChangeDate": "2021-12-02T09:08:53.023Z",
        "thumbnail": "",
        "workbench": {
            "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.1.1",
                "label": "sleeper",
                "inputs": {"input_2": 2, "input_3": False, "input_4": 0},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
            },
            "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.1.1",
                "label": "sleeper_2",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                        "output": "output_1",
                    },
                    "input_2": {
                        "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                        "output": "output_2",
                    },
                    "input_3": False,
                    "input_4": 0,
                },
                "inputNodes": ["ed0ab36a-0939-4406-b6a8-110abd66174e"],
                "parent": None,
                "thumbnail": "",
            },
        },
        "ui": {
            "workbench": {
                "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                    "position": {"x": 406, "y": 158}
                },
                "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                    "position": {"x": 773, "y": 76}
                },
            },
            "slideshow": {},
            "currentNodeId": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
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
    }

    project_in_replace = ProjectAsBody.parse_obj(request_payload)


def test_replace_opened_project_response_model():
    response_body = {
        "data": {
            "uuid": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
            "name": "New Study",
            "description": "",
            "thumbnail": "",
            "prjOwner": "crespo@itis.swiss",
            "creationDate": "2021-12-02T08:57:53.627Z",
            "lastChangeDate": "2021-12-02T09:09:06.744Z",
            "workbench": {
                "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.1.1",
                    "label": "sleeper",
                    "inputs": {"input_2": 2, "input_3": False, "input_4": 0},
                    "inputNodes": [],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.1.1",
                    "label": "sleeper_2",
                    "inputs": {
                        "input_1": {
                            "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                            "output": "output_1",
                        },
                        "input_2": {
                            "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                            "output": "output_2",
                        },
                        "input_3": False,
                        "input_4": 0,
                    },
                    "inputNodes": ["ed0ab36a-0939-4406-b6a8-110abd66174e"],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": ["ed0ab36a-0939-4406-b6a8-110abd66174e"],
                        "currentStatus": "NOT_STARTED",
                    },
                },
            },
            "accessRights": {"103": {"read": True, "write": True, "delete": True}},
            "dev": {},
            "classifiers": [],
            "ui": {
                "mode": "workbench",
                "slideshow": {},
                "workbench": {
                    "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                        "position": {"x": 773, "y": 76}
                    },
                    "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                        "position": {"x": 406, "y": 158}
                    },
                },
                "currentNodeId": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
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
                    "owner": {"user_id": 589, "first_name": "crespo", "last_name": ""},
                    "status": "OPENED",
                },
                "state": {"value": "NOT_STARTED"},
            },
        }
    }

    project_as_body = ProjectAsBody.parse_obj(response_body["data"])


def test_replace_changed_project_request_model():

    # PUT projects/ef6fa0a8-534d-11ec-89f5-02420a0fd439
    request_payload = {
        "uuid": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
        "name": "New Study",
        "description": "",
        "prjOwner": "crespo@itis.swiss",
        "accessRights": {"103": {"read": True, "write": True, "delete": True}},
        "creationDate": "2021-12-02T08:57:53.627Z",
        "lastChangeDate": "2021-12-02T09:08:53.023Z",
        "thumbnail": "",
        "workbench": {
            "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.1.1",
                "label": "sleeper",
                "inputs": {"input_2": 2, "input_3": False, "input_4": 0},
                "inputNodes": [],
                "parent": None,
                "thumbnail": "",
            },
            "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                "key": "simcore/services/comp/itis/sleeper",
                "version": "2.1.1",
                "label": "sleeper_2",
                "inputs": {
                    "input_1": {
                        "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                        "output": "output_1",
                    },
                    "input_2": {
                        "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                        "output": "output_2",
                    },
                    "input_3": False,
                    "input_4": 0,
                },
                "inputNodes": ["ed0ab36a-0939-4406-b6a8-110abd66174e"],
                "parent": None,
                "thumbnail": "",
            },
        },
        "ui": {
            "workbench": {
                "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                    "position": {"x": 406, "y": 158}
                },
                "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                    "position": {"x": 773, "y": 76}
                },
            },
            "slideshow": {},
            "currentNodeId": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
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
    }

    project_in_replace = ProjectAsBody.parse_obj(request_payload)


def test_replace_changed_project_response_model():

    response_body = {
        "data": {
            "uuid": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
            "name": "New Study",
            "description": "",
            "thumbnail": "",
            "prjOwner": "crespo@itis.swiss",
            "creationDate": "2021-12-02T08:57:53.627Z",
            "lastChangeDate": "2021-12-02T09:09:11.111Z",
            "workbench": {
                "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.1.1",
                    "label": "sleeper",
                    "inputs": {"input_2": 2, "input_3": False, "input_4": 0},
                    "inputNodes": [],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": [],
                        "currentStatus": "NOT_STARTED",
                    },
                },
                "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                    "key": "simcore/services/comp/itis/sleeper",
                    "version": "2.1.1",
                    "label": "sleeper_2",
                    "inputs": {
                        "input_1": {
                            "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                            "output": "output_1",
                        },
                        "input_2": {
                            "nodeUuid": "ed0ab36a-0939-4406-b6a8-110abd66174e",
                            "output": "output_2",
                        },
                        "input_3": False,
                        "input_4": 0,
                    },
                    "inputNodes": ["ed0ab36a-0939-4406-b6a8-110abd66174e"],
                    "parent": None,
                    "thumbnail": "",
                    "state": {
                        "modified": True,
                        "dependencies": ["ed0ab36a-0939-4406-b6a8-110abd66174e"],
                        "currentStatus": "NOT_STARTED",
                    },
                },
            },
            "accessRights": {"103": {"read": True, "write": True, "delete": True}},
            "dev": {},
            "classifiers": [],
            "ui": {
                "mode": "workbench",
                "slideshow": {},
                "workbench": {
                    "078b5f85-8ab3-482c-9353-a8ab4c29b9df": {
                        "position": {"x": 773, "y": 76}
                    },
                    "ed0ab36a-0939-4406-b6a8-110abd66174e": {
                        "position": {"x": 406, "y": 158}
                    },
                },
                "currentNodeId": "ef6fa0a8-534d-11ec-89f5-02420a0fd439",
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
                    "owner": {"user_id": 589, "first_name": "crespo", "last_name": ""},
                    "status": "OPENED",
                },
                "state": {"value": "NOT_STARTED"},
            },
        }
    }

    project_as_body = ProjectAsBody.parse_obj(response_body["data"])

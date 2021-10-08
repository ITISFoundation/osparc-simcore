import csv
import json
from pathlib import Path
from typing import Dict, Union

from models_library.database_project_models import (
    ProjectForPgInsert,
    load_projects_exported_as_csv,
)
from models_library.projects import Project, ProjectAtDB
from simcore_service_webserver.version_control_db import ProjectDict, ProjectProxy

JSON_KWARGS = dict(indent=2, sort_keys=True)


def test_it():

    respath = Path("/home/crespo/Downloads/response_1633600264408.json")
    csvpath = Path("/home/crespo/Downloads/projects.csv")

    reponse_body = json.loads(respath.read_text())

    project_api_dict = reponse_body["data"]
    with open("project_api_dict.json", "wt") as fh:
        print(json.dumps(project_api_dict, **JSON_KWARGS), file=fh)

    project_api_model = Project.parse_obj(project_api_dict)
    with open("project_api_model.json", "wt") as fh:
        print(
            project_api_model.json(by_alias=True, exclude_unset=True, **JSON_KWARGS),
            file=fh,
        )

    project_db_model = load_projects_exported_as_csv(csvpath, delimiter=";")[0]
    with open("project_db_model.json", "wt") as fh:
        print(
            project_db_model.json(by_alias=True, exclude_unset=True, **JSON_KWARGS),
            file=fh,
        )

    # given a api_project_model -> convert it into a db project model

    obj = project_api_model.dict(exclude_unset=True)
    obj["prj_owner"] = 3  # email -> int
    new_project_db_model = ProjectForPgInsert.parse_obj(obj)

    with open("new_project_db_model.json", "wt") as fh:
        print(
            new_project_db_model.to_values(**JSON_KWARGS),
            file=fh,
        )

    # obj.dict(exclude=)

    # elimitate excess
    # ProjectAtDB.Config.extra = Extra.allow

    # transform email -> id
    obj["prj_owner"] = 1

    # add in db but not in obj?
    # id is not required
    #

    # m = ProjectAtDB.parse_obj({  ,**api_project_model.dict()})

    # with open("db_project_model2.json", "wt") as fh:
    #     print(
    #         m.json(
    #             by_alias=True, exclude_unset=True, **JSON_KWARGS
    #         ),
    #         file=fh,
    #     )


def test_that():

    from pydantic import BaseModel, Json

    class S(BaseModel):
        json_obj: Union[Dict, Json]

    ss = S(json_obj='{"x": 3, "y": {"z": 2}}')
    print(ss.json_obj, type(ss.json_obj))

    ss = S(json_obj={"x": 3, "y": {"z": 2}})
    print(ss.json_obj, type(ss.json_obj))

    ss = S(json_obj="[1, 2, 3 ]")
    print(ss.json_obj, type(ss.json_obj))
    ss = S(json_obj=[1, 2, 3])
    print(ss.json_obj, type(ss.json_obj))

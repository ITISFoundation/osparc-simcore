import csv
import json
from pathlib import Path
from typing import Dict, Union

from models_library.database_project import (
    ProjectFromCsv,
    load_projects_exported_as_csv,
)
from models_library.projects import Project, ProjectAtDB
from pydantic.main import Extra
from simcore_service_webserver.version_control_db import ProjectDict, ProjectProxy

JSON_KWARGS = dict(indent=2, sort_keys=True)


def test_it():

    respath = Path("/home/crespo/Downloads/response_1633600264408.json")
    csvpath = Path("/home/crespo/Downloads/projects.csv")

    reponse_body = json.loads(respath.read_text())

    api_project_dict = reponse_body["data"]
    with open("api_project_dict.json", "wt") as fh:
        print(json.dumps(api_project_dict, **JSON_KWARGS), file=fh)

    api_project_model = Project.parse_obj(api_project_dict)
    with open("api_project_model.json", "wt") as fh:
        print(
            api_project_model.json(by_alias=True, exclude_unset=True, **JSON_KWARGS),
            file=fh,
        )

    db_project_model = load_projects_exported_as_csv(csvpath, delimiter=";")[0]
    with open("db_project_model.json", "wt") as fh:
        print(
            db_project_model.json(by_alias=True, exclude_unset=True, **JSON_KWARGS),
            file=fh,
        )

    # given a api_project_model -> convert it into a db project model

    obj = api_project_model.dict(exclude_unset=True)

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

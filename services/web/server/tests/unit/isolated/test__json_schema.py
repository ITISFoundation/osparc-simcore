import json
from pathlib import Path

from servicelib.aiohttp import jsonschema_validation
from simcore_service_webserver._resources import resources


def test_validate_project_json_schema():
    CURRENT_DIR = Path(__file__).resolve().parent

    with open(CURRENT_DIR / "data/project-data.json") as f:
        project = json.load(f)

    # NOTE: Mar.2023 Previous project-v0.0.1.json schema is passing validation
    # even though it should fail. The reason is there is wrongly defined
    # pattern properties in workbench which is ignored in practice.
    # Current: "^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?4[0-9a-fA-F]{3}-?[89abAB][0-9a-fA-F]{3}-?[0-9a-fA-F]{12}$"
    # Should be: "^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
    with resources.stream("api/v0/schemas/project-v0.0.1.json") as fh:
        old_project_schema = json.load(fh)
    assert jsonschema_validation.validate_instance(project, old_project_schema) is None

    # This is new Pydantic generated json schema, that was modified
    # so it works as the previous one. This should be fixed in:
    # https://github.com/ITISFoundation/osparc-simcore/issues/3992
    with resources.stream("api/v0/schemas/project-v0.0.1-pydantic.json") as fh:
        new_project_schema = json.load(fh)

    assert new_project_schema["properties"]["workbench"]["patternProperties"][
        "^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
    ]
    assert new_project_schema["properties"]["ui"]["properties"]["workbench"][
        "patternProperties"
    ][
        "^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
    ]

    # We have to remove patternProperties from the schema, this is done
    # here: setup_projects_model_schema() in projects_models.py until #3992 is fixed
    new_project_schema["properties"]["workbench"].pop("patternProperties")
    new_project_schema["properties"]["ui"]["properties"]["workbench"].pop(
        "patternProperties"
    )
    assert jsonschema_validation.validate_instance(project, new_project_schema) is None

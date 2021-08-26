# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy
from typing import Any, Dict, List, Type

import pytest
from faker import Faker
from models_library.projects import Project
from models_library.utils.database_models_factory import (
    convert_sa_table_to_pydantic_model,
)
from pydantic import BaseModel
from pydantic.fields import ModelField
from pytest_simcore.helpers.rawdata_fakers import random_project
from simcore_postgres_database.models.base import Base
from simcore_postgres_database.models.projects import projects


@pytest.fixture()
def minimal_project(faker: Faker) -> Dict[str, Any]:
    # API request body payload
    return {
        "uuid": faker.uuid4(),
        "name": "The project name",
        "description": "The project's description",
        "prjOwner": "theowner@ownership.com",
        "accessRights": {},
        "thumbnail": None,
        "creationDate": "2019-05-24T10:36:57.813Z",
        "lastChangeDate": "2019-05-24T10:36:57.813Z",
        "workbench": {},
    }


ProjectOrmBase = convert_sa_table_to_pydantic_model(
    projects, include_server_defaults=True
)


class ProjectOrm(ProjectOrmBase):
    pass


def extract_examples(fake_cls: Type[BaseModel]) -> List[Dict[str, Any]]:

    examples = []

    if config_cls := getattr(fake_cls, "Config"):
        if schema_extra := getattr(config_cls, "schema_extra", {}):
            examples = schema_extra.get("examples", [])
            if example := schema_extra.get("example"):
                examples.append(example)

    return examples


def create_fake_obj(fake_cls: Type[BaseModel], faker: Faker):

    examples = []

    if (config_cls := getattr(fake_cls, "Config")) and (
        schema_extra := getattr(config_cls, "schema_extra", {})
    ):
        examples = schema_extra.get("examples", [])
        if example := schema_extra.get("example"):
            examples.append(example)

    fake_obj = {}

    field_name: str
    field_model: ModelField
    for field_name, field_model in fake_cls.__fields__.items():

        if not field_model.required:
            continue

        key = field_model.alias
        value = field_model.default
        type_ = field_model.type_

        guess_name = field_name.lower()

        # policies based on type_, guess_name

        if issubclass(type_, str):
            if "description" in guess_name:
                value = faker.sentence()
            if "name" in guess_name:
                value = faker.word()
        elif issubclass(type_, BaseModel):
            value = create_fake_obj(type_, faker)

        if value:
            fake_obj[key] = value

    # by field type
    # by table.column defaults
    # by example

    return fake_obj


@pytest.fixture
def project_from_database(faker: Faker):
    snapshot = faker.date_time()

    project_orm = ProjectOrm.parse_obj(
        random_project(
            uuid=faker.uuid4(),
            name=faker.word(),
            description=faker.sentence(),
            prj_owner=faker.pyint(),
            thumbnail=faker.image_url(width=120, height=120),
            access_rights={},
            workbench={},
            # produced on server side
            id=faker.pyint(min_value=0),
            # these here are created by ProjectOrm using defaults
            # creation_date=snapshot,
            # last_change_date=snapshot,
            # ui={},
            # classifiers=[],
            # dev={},
            # quality={}
        )
    )

    return project_orm


def test_it(project_from_database):
    print(project_from_database.json(indent=2))


def test_project_minimal_model(minimal_project: Dict[str, Any]):
    project = Project.parse_obj(minimal_project)
    assert project

    assert project.thumbnail == None


def test_project_with_thumbnail_as_empty_string(minimal_project: Dict[str, Any]):
    thumbnail_empty_string = deepcopy(minimal_project)
    thumbnail_empty_string.update({"thumbnail": ""})
    project = Project.parse_obj(thumbnail_empty_string)

    assert project
    assert project.thumbnail == None


def test_project_type_in_models_package_same_as_in_postgres_database_package():
    from models_library.projects import ProjectType as ml_project_type
    from simcore_postgres_database.models.projects import ProjectType as pg_project_type

    # pylint: disable=no-member
    assert (
        ml_project_type.__members__.keys() == pg_project_type.__members__.keys()
    ), f"The enum in models_library package and postgres package shall have the same values. models_pck: {ml_project_type.__members__}, postgres_pck: {pg_project_type.__members__}"

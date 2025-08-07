# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from faker import Faker
from models_library.projects_nodes import Node
from pydantic import TypeAdapter, ValidationError
from pytest_simcore.helpers.faker_factories import random_phone_number
from simcore_postgres_database.utils_projects_nodes import (
    ProjectNode,
    ProjectNodeCreate,
)
from simcore_service_webserver.users._controller.rest._rest_schemas import (
    MyPhoneRegister,
    PhoneNumberStr,
)


@pytest.mark.parametrize(
    "phone",
    [
        "+41763456789",
        "+19104630364",
        "+1 301-304-4567",
        "+41763456686",
        "+19104630873",
        "+19104630424",
        "+34 950 453 772",
        "+19104630700",
        "+13013044719",
    ],
)
def test_valid_phone_numbers(phone: str):
    # This test is used to tune options of PhoneNumberValidator
    assert MyPhoneRegister.model_validate({"phone": phone}).phone == TypeAdapter(
        PhoneNumberStr
    ).validate_python(phone)


def test_random_phone_number():
    # This test is used to tune options of PhoneNumberValidator
    for _ in range(10):
        phone = random_phone_number(Faker(seed=42))
        assert MyPhoneRegister.model_validate({"phone": phone}).phone == TypeAdapter(
            PhoneNumberStr
        ).validate_python(phone)


@pytest.mark.parametrize(
    "phone",
    [
        "+41763456789",
        "+41 76 345 67 89",
        "tel:+41-76-345-67-89",
    ],
    ids=["E.164", "INTERNATIONAL", "RFC3966"],
)
def test_autoformat_phone_number_to_e164(phone: str):
    # This test is used to tune options of PhoneNumberValidator formatting to E164
    assert TypeAdapter(PhoneNumberStr).validate_python(phone) == "+41763456789"


@pytest.mark.parametrize(
    "phone",
    ["41763456789", "+09104630364", "+1 111-304-4567"],
)
def test_invalid_phone_numbers(phone: str):
    # This test is used to tune options of PhoneNumberValidator
    with pytest.raises(ValidationError):
        MyPhoneRegister.model_validate({"phone": phone})


_node_examples = Node.model_json_schema()["examples"]


@pytest.mark.parametrize(
    "node_data",
    _node_examples,
    ids=[f"example-{i}" for i in range(len(_node_examples))],
)
def test_adapters_between_project_node_models(node_data: dict, faker: Faker):
    # -> to Node
    node_id = faker.uuid4()
    node = Node.model_validate(node_data)

    # -> to ProjectNodeCreate and ProjectNode
    project_node_create = ProjectNodeCreate(
        node_id=node_id,
        **node.model_dump(by_alias=False, mode="json"),
    )
    project_node = ProjectNode(
        node_id=node_id,
        created=faker.date_time(),
        modified=faker.date_time(),
        **node.model_dump(by_alias=False, mode="json"),
    )

    # -> to Node
    assert (
        Node.model_validate(project_node_create.model_dump_as_node(), by_name=True)
        == node
    )
    assert Node.model_validate(project_node.model_dump_as_node(), by_name=True) == node

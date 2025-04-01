# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable, Coroutine
from typing import Any

from models_library.products import ProductName
from models_library.users import UserID
from notifications_library._models import UserData
from notifications_library._repository import TemplatesRepo, UsersRepo
from sqlalchemy.ext.asyncio.engine import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_user_data_repo(
    sqlalchemy_async_engine: AsyncEngine,
    user: dict,
    user_id: UserID,
    user_data: UserData,
):
    assert user["id"] == user_id

    repo = UsersRepo(sqlalchemy_async_engine)
    got = await repo.get_user_data(user_id)
    assert got == user_data


async def test_templates_repo(
    sqlalchemy_async_engine: AsyncEngine,
    email_templates: dict[str, Any],
    email_template_mark: dict,
    product_name: ProductName,
    set_template_to_product: Callable[[str, ProductName], Coroutine],
):
    repo = TemplatesRepo(sqlalchemy_async_engine)

    one_template_name = next(_ for _ in email_templates if "email" in _)
    await set_template_to_product(one_template_name, product_name)

    async for template in repo.iter_email_templates(product_name):
        assert template.name in email_templates
        assert email_template_mark in template.content
        assert template.name == one_template_name

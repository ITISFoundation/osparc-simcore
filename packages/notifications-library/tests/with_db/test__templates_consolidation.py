from pathlib import Path

from notifications_library._db import TemplatesRepo
from notifications_library._templates import (
    consolidate_templates,
    get_folder_stats_msg,
    print_tree,
)
from sqlalchemy.ext.asyncio.engine import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_templates_consolidation(
    tmp_path: Path, sqlalchemy_async_engine: AsyncEngine, products_names: list[str]
):
    new_templates_dir = tmp_path / "all-templates"
    new_templates_dir.mkdir()

    repo = TemplatesRepo(sqlalchemy_async_engine)
    await consolidate_templates(new_templates_dir, products_names, repo)
    print_tree(new_templates_dir)

    print(get_folder_stats_msg(new_templates_dir))

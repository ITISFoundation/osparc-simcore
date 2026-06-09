from pathlib import Path

from notifications_library._repository import TemplatesRepo
from notifications_library._templates import _print_tree, consolidate_templates
from sqlalchemy.ext.asyncio.engine import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


async def test_templates_consolidation(tmp_path: Path, sqlalchemy_async_engine: AsyncEngine, products_names: list[str]):
    # Create a minimal templates directory for testing
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    (templates_dir / "test_template.j2").write_text("Hello {{ name }}")

    new_templates_dir = tmp_path / "all-templates"
    new_templates_dir.mkdir()

    repo = TemplatesRepo(sqlalchemy_async_engine)
    await consolidate_templates(templates_dir, new_templates_dir, products_names, repo)

    _print_tree(new_templates_dir)

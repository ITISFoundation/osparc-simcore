import shutil
from pathlib import Path

from models_library.products import ProductName
from notifications_library._models import ProductData
from notifications_library._render import (
    create_render_env_from_folder,
    create_render_env_from_package,
)
from notifications_library._templates import _print_tree, _templates_dir


def test_render_env_from_folder(
    tmp_path: Path, product_name: ProductName, product_data: ProductData
):

    pkg_env = create_render_env_from_package()

    top_dir = tmp_path / "consolidated"
    top_dir.mkdir()

    product_name_dir = top_dir / product_name
    shutil.copytree(_templates_dir, product_name_dir)
    shutil.copytree(_templates_dir, top_dir / "osparc")

    _print_tree(top_dir)

    consolidated_env = create_render_env_from_folder(top_dir)

    product_template = consolidated_env.get_template(f"{product_name}/base.html")
    common_template = pkg_env.get_template("base.html")

    data = {"product": product_data}
    assert product_template.render(data) == common_template.render(data)

import importlib.resources
import logging
import shutil
from pathlib import Path

from models_library.products import ProductName

from ._db import TemplatesRepo

_logger = logging.getLogger(__name__)


_td = importlib.resources.files("notifications_library.templates")
_templates_dir = Path(f"{_td}")

#
# templates naming is formatted as "{event_name}.{provider}.{part}.{format}"
#


def get_email_templates(event_name: str) -> dict[str, Path]:
    return {p.name: p for p in _templates_dir.glob(f"{event_name}.email.*")}


def get_folder_stats_msg(top_dir: Path) -> str:
    assert top_dir.is_dir()  # nosec
    file_count = sum(1 for _ in top_dir.glob("**/*") if _.is_file())
    total_size = sum(_.stat().st_size for _ in top_dir.glob("**/*") if _.is_file())
    return f"Files: {file_count}, Total Size: {total_size} bytes"


async def consolidate_templates(
    new_dir: Path, product_names: list[ProductName], repo: TemplatesRepo
):
    """Builds a folder structure with all templates for each product

    new_dir:
        product_1:
            template1
            ...
        product_2:
            template1
            ...

    """
    assert new_dir.is_dir()  # nosec

    for product_name in product_names:
        product_folder = new_dir / product_name
        product_folder.mkdir(parents=True, exist_ok=True)

        # takes common as defaults
        for p in _templates_dir.iterdir():
            if p.is_file():
                shutil.copy(p, product_folder / p.name, follow_symlinks=False)

        # overrides with customs in-place
        if (_templates_dir / product_name).exists():
            for p in (_templates_dir / product_name).iterdir():
                if p.is_file():
                    shutil.copy(p, product_folder / p.name, follow_symlinks=False)

        # overrides with customs in database
        async for custom_template in repo.iter_product_templates(product_name):
            assert custom_template.product_name == product_name  # nosec

            template_path = product_folder / custom_template.name
            template_path.write_text(custom_template.content)

        _logger.debug(
            "%s %s", f"{product_folder=}", get_folder_stats_msg(product_folder)
        )

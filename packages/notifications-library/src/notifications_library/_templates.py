import importlib.resources
import logging
import shutil
from pathlib import Path
from typing import NamedTuple

import notifications_library
from aiofiles.os import wrap as sync_to_async
from models_library.products import ProductName

from ._db import TemplatesRepo

_logger = logging.getLogger(__name__)


_resources = importlib.resources.files(notifications_library.__name__).joinpath(
    "templates"
)
_templates_dir = Path(_resources.as_posix())


class NamedTemplateTuple(NamedTuple):
    # Named templates are named as "{event_name}.{provider}.{part}.{format}"
    #
    # e.g. base.html is a generic template vs on_payed.email.content.html that is a named template
    #
    event: str
    media: str
    part: str
    ext: str


_TEMPLATE_NAME_SEPARATOR = "."


def split_template_name(template_name: str) -> NamedTemplateTuple:
    return NamedTemplateTuple(*template_name.split(_TEMPLATE_NAME_SEPARATOR))


def get_default_named_templates(
    event: str = "*", media: str = "*", part: str = "*", ext: str = "*"
) -> dict[str, Path]:
    pattern = _TEMPLATE_NAME_SEPARATOR.join([event, media, part, ext])
    return {p.name: p for p in _templates_dir.glob(pattern)}


def _print_tree(top: Path, indent=0, prefix="", **print_kwargs):
    prefix = indent * "    " + prefix
    if top.is_file():
        file_size = f"{top.stat().st_size}B"
        entry = f"{top.name:<50}{file_size}"
        print(prefix + entry, **print_kwargs)  # noqa: T201
    elif top.is_dir():
        children = sorted(top.iterdir())
        entry = f"{top.name}  {len(children)}"
        print(prefix + entry, **print_kwargs)  # noqa: T201
        for child in children[:-1]:
            _print_tree(child, indent + 1, "├── ", **print_kwargs)
        if children:
            _print_tree(children[-1], indent + 1, "└── ", **print_kwargs)


_aioshutil_copy = sync_to_async(shutil.copy)


async def _copy_files(src: Path, dst: Path):
    for p in src.iterdir():
        if p.is_file():
            await _aioshutil_copy(p, dst / p.name, follow_symlinks=False)


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
        await _copy_files(_templates_dir, product_folder)

        # overrides with customs in-place
        if (_templates_dir / product_name).exists():
            await _copy_files(_templates_dir / product_name, product_folder)

        # overrides with customs in database
        async for custom_template in repo.iter_product_templates(product_name):
            assert custom_template.product_name == product_name  # nosec

            template_path = product_folder / custom_template.name
            template_path.write_text(custom_template.content)

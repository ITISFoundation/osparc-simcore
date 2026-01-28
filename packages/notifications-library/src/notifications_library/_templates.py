import importlib.resources
import logging
import os
import shutil
from pathlib import Path
from typing import Final, NamedTuple

import aiofiles
from aiofiles.os import wrap as sync_to_async
from models_library.products import ProductName

import notifications_library

from ._repository import TemplatesRepo

_logger = logging.getLogger(__name__)


_templates = importlib.resources.files(notifications_library.__name__).joinpath("templates")
_templates_dir = Path(os.fspath(_templates))  # type:ignore

# Templates are organised as:
#
#  - named-templates: have a hierarchical names used to identify the event, provider (e.g. email, sms),
#     part of the message (e.g. subject, content) and format (e.g. html or txt). (see test__templates.py)
#  - generic: are used in other templates (can be seen as "templates of templates")
#
#    e.g. _base/body_html.j2 is a generic template vs email/paid/body_html.j2 that is a named template


class NamedTemplateTuple(NamedTuple):
    # Named templates are stored as {channel}/{template_name}/{part}.{format}"
    channel: str
    template_name: str
    part: str
    ext: str


_TEMPLATE_NAME_SEPARATOR: Final[str] = "/"
_TEMPLATE_NAME_PARTS_COUNT: Final[int] = 3


def split_template_name(template_name: str) -> NamedTemplateTuple:
    parts = template_name.split(_TEMPLATE_NAME_SEPARATOR)
    if len(parts) != _TEMPLATE_NAME_PARTS_COUNT:
        msg = f"Invalid template name format: {template_name}"
        raise TypeError(msg)
    channel, template_id, filename = parts
    part, ext = filename.rsplit(".", 1)
    return NamedTemplateTuple(channel, template_id, part, ext)


def get_default_named_templates(
    channel: str = "*", template_name: str = "*", part: str = "*", ext: str = "*"
) -> dict[str, Path]:
    # If all parameters are specific (no wildcards), try direct path first
    if channel != "*" and template_name != "*" and part != "*" and ext != "*":
        filename = f"{part}.{ext}"
        direct_path = _templates_dir / channel / template_name / filename
        if direct_path.exists():
            template_id = _TEMPLATE_NAME_SEPARATOR.join([channel, template_name, filename])
            return {template_id: direct_path}

    # Otherwise use glob pattern matching
    pattern = _TEMPLATE_NAME_SEPARATOR.join([channel, template_name, f"{part}.{ext}"])
    result = {}
    for p in _templates_dir.glob(pattern):
        # Build the template name as channel/template_name/filename
        relative_path = p.relative_to(_templates_dir)
        template_id = _TEMPLATE_NAME_SEPARATOR.join(relative_path.parts)
        result[template_id] = p
    return result


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


async def consolidate_templates(new_dir: Path, product_names: list[ProductName], repo: TemplatesRepo):
    """Consolidates all templates in new_dir folder for each product

    Builds a structure under new_dir and dump all templates (T) for each product (P) with the following
    precedence rules:
        1. T found in *database* associated to P in products_to_templates.join(jinja2_templates), otherwise
        2. found in notifications_library/templates/P/T *file*, otherwise
        3. found in notifications_library/T *file*

    After consolidation, the tree dir would have the follow structure
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
            async with aiofiles.open(template_path, "w") as fh:
                await fh.write(custom_template.content)

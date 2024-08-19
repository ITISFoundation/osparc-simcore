# mypy: disable-error-code=truthy-function
from ._utils import convert_groups_db_to_schema

assert convert_groups_db_to_schema  # nosec

__all__: tuple[str, ...] = ("convert_groups_db_to_schema",)

from pydantic_core import PydanticUndefined

# SEE https://github.com/fastapi/fastapi/blob/master/fastapi/_compat.py#L75-L78
#
# Use as default when default_factory
Undefined = PydanticUndefined

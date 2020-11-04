import warnings

from ._meta import __version__

#
# NOTE: Some BaseSettings are using aliases (e.g. version for vtag) to facility construct
#  pydantic settings from names defined in trafaret schemas for the config files
#
warnings.filterwarnings(
    "ignore",
    message='aliases are no longer used by BaseSettings to define which environment variables to read. Instead use the "env" field setting. See https://pydantic-docs.helpmanual.io/usage/settings/#environment-variable-names',
)

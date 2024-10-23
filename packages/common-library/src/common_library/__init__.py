""" osparc's service common library

"""

#
# NOTE:
#   - "examples" = [ ...] keyword and NOT "example". See https://json-schema.org/understanding-json-schema/reference/generic.html#annotations
#

from importlib.metadata import version

__version__: str = version("simcore-common-library")

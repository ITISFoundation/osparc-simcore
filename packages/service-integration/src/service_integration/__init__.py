"""Library to facilitate the integration of user services running in osparc-simcore"""

from . import _patch
from ._meta import __version__

_patch.patch_osparc_variable_identifier()

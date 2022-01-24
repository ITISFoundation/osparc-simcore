from typing import Dict, Optional

EnvVarsDict = Dict[str, Optional[str]]
#
# NOTE: that this means that env vars do not require a value. If that happens a None is assigned
#   For instance, a env file as
#
#   NAME=foo
#   ONLY_NAME=
#
# will return env: EnvVarsDict = {"NAME": "foo", "ONLY_NAME": None}
#

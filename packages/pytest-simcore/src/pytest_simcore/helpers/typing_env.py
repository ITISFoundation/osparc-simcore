from typing import Dict, Optional

EnvVarsDict = Dict[str, Optional[str]]
#
# NOTE: that this means that env vars do not require a value. If that happens a None is assigned
#   For instance, a valid env file is
#
#   NAME=foo
#   INDEX=33
#   ONLY_NAME=
#
# will return env: EnvVarsDict = {"NAME": "foo", "INDEX": 33, "ONLY_NAME": None}
#

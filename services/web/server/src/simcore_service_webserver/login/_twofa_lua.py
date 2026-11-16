"""Loads the Redis Lua scripts of the 2FA trial budget and resend cooldown

The scripts live in the ``lua/`` package directory so they can be linted with
StyLua (see ``.pre-commit-config.yaml``). SEE servicelib.redis._semaphore_lua
for the same loading pattern.
"""

from typing import Annotated, Final

from annotated_types import doc
from servicelib.utils import load_script

_SCRIPTS_PACKAGE: Final[Annotated[str, doc("package directory holding the 2FA Lua scripts")]] = (
    "simcore_service_webserver.login.lua"
)

CONSUME_TRIAL_SCRIPT: Final[
    Annotated[
        str, doc("charges one trial of the current code's budget; see lua/consume_trial.lua for the KEYS/ARGV contract")
    ]
] = load_script(_SCRIPTS_PACKAGE, "consume_trial")

CONSUME_MATCHED_CODE_SCRIPT: Final[
    Annotated[
        str, doc("deletes a matched code exactly once; see lua/consume_matched_code.lua for the KEYS/ARGV contract")
    ]
] = load_script(_SCRIPTS_PACKAGE, "consume_matched_code")

RELEASE_COOLDOWN_SCRIPT: Final[
    Annotated[
        str,
        doc(
            "deletes a resend cooldown only its owner can; see lua/release_resend_cooldown.lua"
            " for the KEYS/ARGV contract"
        ),
    ]
] = load_script(_SCRIPTS_PACKAGE, "release_resend_cooldown")

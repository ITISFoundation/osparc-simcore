import logging
import os

log = logging.getLogger(__name__)


def has_datcore_tokens() -> bool:
    # TODO: activate tests against BF services in the CI.
    #
    # CI shall add BF_API_KEY, BF_API_SECRET environs as secrets
    #
    if not os.environ.get("BF_API_KEY") or not os.environ.get("BF_API_SECRET"):
        return False
    return True

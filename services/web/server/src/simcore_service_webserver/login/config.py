""" login subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T

from .cfg import DEFAULTS

CONFIG_SECTION_NAME = 'login'

# TODO: merge with cfg.py
schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Bool(),
    T.Key("registration_confirmation_required", default=DEFAULTS["REGISTRATION_CONFIRMATION_REQUIRED"], optional=True): T.Or(T.Bool, T.Int),
})

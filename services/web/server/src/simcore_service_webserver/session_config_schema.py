""" session subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T

CONFIG_SECTION_NAME = "session"

schema = T.Dict({"secret_key": T.String})

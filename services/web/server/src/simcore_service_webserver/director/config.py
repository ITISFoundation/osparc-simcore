""" director subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T


CONFIG_SECTION_NAME = 'director'

schema = T.Dict({
    "host": T.String(),
    "port": T.Int()
})

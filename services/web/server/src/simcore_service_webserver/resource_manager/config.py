""" resource manager subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T

CONFIG_SECTION_NAME = 'resource_manager'

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Or(T.Bool(), T.Int()),
})

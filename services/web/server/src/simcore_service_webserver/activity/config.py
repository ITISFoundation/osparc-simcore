""" projects activity's configuration

    - config-file schema
    - settings
"""
import trafaret as T

CONFIG_SECTION_NAME = "activity"

schema = T.Dict({
    T.Key("enabled", default=True, optional=True): T.Bool(),
})

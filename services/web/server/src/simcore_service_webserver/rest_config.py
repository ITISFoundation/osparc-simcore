""" rest subsystem's configuration

    - config-file schema
    - settings
"""
import trafaret as T


CONFIG_SECTION_NAME = 'rest'


schema = T.Dict({
    "oas": T.Dict({
        "version": T.String, # TODO: v0, v1, etc
        "location": T.Or(T.String, T.URL)   # either path or url should contain version in it
    })
})

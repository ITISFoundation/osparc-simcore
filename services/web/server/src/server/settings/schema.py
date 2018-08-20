""" Configuration file's schema

TODO: add more strict checks with re
TODO: add support for versioning
"""
__version__ = "1.0"

import trafaret as T


T_DIRECTOR = T.Dict({
    "host": T.String(),
    "port": T.Int()
})

T_POSTGRES = T.Dict({
    "database": T.String(),
    "user": T.String(),
    "password": T.String(),
    "host": T.String(),
    "port": T.Int(),
    "minsize": T.Int(),
    "maxsize": T.Int(),
    "endpoint": T.String()
})

T_RABBIT = T.Dict({
    "user": T.String(),
    "password": T.String(),
    "channels": T.Dict({
        "progress": T.String(),
        "log": T.String(),
    })

})

T_S3 = T.Dict({
    "endpoint": T.String(),
    "access_key": T.String(),
    "secret_key": T.String(),
    "bucket_name": T.String(),
})

T_CS_S4L = T.Dict({
    "host": T.String(),
    "app": T.Dict({
        "port": T.Int()
    }),
    "modeler": T.Dict({
        "port": T.Int()
    }),
})


OPTIONS_SCHEMA = T.Dict({
    "version": T.String(),
    T.Key("postgres"): T_POSTGRES,
    T.Key("s3"): T_S3,
    T.Key("cs_s4l"): T_CS_S4L,
    "host": T.IP,
    "port": T.Int(),
    "client_outdir": T.String(),
    "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL"),
    "testing": T.Bool()
})

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
    T.Key("minsize", default=1 ,optional=True): T.Int(),
    T.Key("maxsize", default=4, optional=True): T.Int(),
    "host": T.Or( T.String, T.Null),
    "port": T.Or( T.Int, T.Null),
    "endpoint": T.Or( T.String, T.Null)
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


T_THIS_APP = T.Dict({
    "host": T.IP,
    "port": T.Int(),
    "client_outdir": T.String(),
    "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL"),
    "testing": T.Bool()
})


OPTIONS_SCHEMA = T.Dict({
    "version": T.String(),
    T.Key("app"): T_THIS_APP,
    T.Key("director"): T_DIRECTOR,
    T.Key("postgres"): T_POSTGRES,
    T.Key("rabbit"): T_RABBIT,
    T.Key("s3"): T_S3,
    T.Key("cs_s4l"): T_CS_S4L
})

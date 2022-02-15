import trafaret as T

CONFIG_SECTION_NAME = "login"

# TODO: merge with cfg.py
schema = T.Dict(
    {
        T.Key("enabled", default=True, optional=True): T.Bool(),
        T.Key(
            "registration_confirmation_required",
            default=True,
            optional=True,
        ): T.Or(T.Bool, T.ToInt),
        T.Key("registration_invitation_required", default=False, optional=True): T.Or(
            T.Bool, T.ToInt
        ),
    }
)

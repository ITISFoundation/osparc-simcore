import trafaret as T


def addon_section(name: str, optional: bool = False) -> T.Key:
    if optional:
        return T.Key(name, default=dict(enabled=True), optional=optional)
    return T.Key(name)


def minimal_addon_schema() -> T.Dict:
    return T.Dict({T.Key("enabled", default=True, optional=True): T.Bool()})

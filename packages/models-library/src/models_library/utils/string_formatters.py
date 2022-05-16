def snake_to_camel(subject: str) -> str:
    """

    Usage in pydantic:

    [...]
        class Config:
            extra = Extra.forbid
            alias_generator = snake_to_camel  # <--------
            json_loads = orjson.loads
            json_dumps = json_dumps

    """
    parts = subject.lower().split("_")
    return parts[0] + "".join(word.title() for word in parts[1:])

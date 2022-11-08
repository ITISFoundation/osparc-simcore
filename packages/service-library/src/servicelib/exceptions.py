class InvalidConfig(ValueError):
    # NOTE: If your service can’t load the config on startup for any reason, it should just crash
    # SEE https://www.willett.io/posts/precepts/
    pass

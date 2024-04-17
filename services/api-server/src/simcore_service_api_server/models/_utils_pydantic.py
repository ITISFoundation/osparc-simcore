from servicelib.json_serialization import OrJsonAdapter


class BaseConfig:
    json_loads = OrJsonAdapter.loads
    json_dumps = OrJsonAdapter.dumps

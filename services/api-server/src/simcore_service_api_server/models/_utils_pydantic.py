from servicelib.json_serialization import orjson_dumps, orjson_loads


class BaseConfig:
    json_loads = orjson_loads
    json_dumps = orjson_dumps

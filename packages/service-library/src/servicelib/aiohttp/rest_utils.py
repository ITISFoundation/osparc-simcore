import json
from dataclasses import asdict


class EnvelopeFactory:
    """
    Creates a { 'data': , 'error': } envelop for response payload

    as suggested in https://medium.com/studioarmix/learn-restful-api-design-ideals-c5ec915a430f
    """

    def __init__(self, data=None, error=None):
        enveloped = {"data": data, "error": error}
        for key, value in enveloped.items():
            if value is not None and not isinstance(value, dict):
                enveloped[key] = asdict(value)
        self._envelope = enveloped

    def as_dict(self) -> dict:
        return self._envelope

    def as_text(self) -> str:
        return json.dumps(self.as_dict())

    as_data = as_dict

""" rest - json data encoders/decodes

"""
import attr
import json


class DataEncoder(json.JSONEncoder):
    """
        Customized json encoder for rest data models

        Extra encoding of:
            - attr.s-like classes

    TODO: extend to more types like apiset
    """
    def default(self, o): #pylint: disable=E0202
        if attr.has(o.__class__):
            return attr.asdict(o)
        return json.JSONEncoder.default(self, o)


def jsonify(payload):
    return json.dumps(payload, cls=DataEncoder)

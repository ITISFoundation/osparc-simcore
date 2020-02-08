import json


DAG_WORKBENCH_JSON = '''\
{
 "additionalProp1": {
    "key": "string",
    "version": "string",
    "label": "string",
    "progress": 0,
    "thumbnail": "string",
    "inputs": {
    "additionalProp1": {},
    "additionalProp2": {},
    "additionalProp3": {}
    },
    "inputAccess": {},
    "inputNodes": [
    "string"
    ],
    "outputs": {
    "additionalProp1": {},
    "additionalProp2": {},
    "additionalProp3": {}
    },
    "parent": "string",
    "position": {
    "x": 0,
    "y": 0
    }
    },
  "additionalProp2": {
      "key": "string",
      "version": "string",
      "label": "string",
      "progress": 0,
      "thumbnail": "string",
      "inputs": {
        "additionalProp1": {},
        "additionalProp2": {},
        "additionalProp3": {}
      },
      "inputAccess": {},
      "inputNodes": [
        "string"
      ],
      "outputs": {
        "additionalProp1": {},
        "additionalProp2": {},
        "additionalProp3": {}
      },
      "parent": "string",
      "position": {
        "x": 0,
        "y": 0
      }
    },
    "additionalProp3": {
      "key": "string",
      "version": "string",
      "label": "string",
      "progress": 0,
      "thumbnail": "string",
      "inputs": {
        "additionalProp1": {},
        "additionalProp2": {},
        "additionalProp3": {}
      },
      "inputAccess": {},
      "inputNodes": [
        "string"
      ],
      "outputs": {
        "additionalProp1": {},
        "additionalProp2": {},
        "additionalProp3": {}
      },
      "parent": "string",
      "position": {
        "x": 0,
        "y": 0
      }
    }
}
'''.strip()



DAG_WORKBENCH_DICT = json.loads(DAG_WORKBENCH_JSON)

from typing import Dict
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

app = FastAPI()


@app.get("/")
async def read_main():
    return {"msg": "Hello World"}


workbench_sample = {
    "262ff3b6-a151-5231-9ddf-df24c698b8aa": {
        "key": "simcore/services/dynamic/electrode-selector",
        "version": "1.0.0",
        "label": "Setup",
        "inputs": {},
        "inputAccess": {"input_1": "Invisible"},
        "inputNodes": [],
        "thumbnail": "",
        "position": {"x": 42, "y": 98},
    },
    "9ed12c45-0bd7-5acf-98ab-bf7568ee5da5": {
        "key": "simcore/services/comp/ti-solutions-optimizer",
        "version": "1.0.0",
        "label": "Optimizer",
        "inputs": {"input_1": "some_value(optional)"},
        "inputNodes": ["262ff3b6-a151-5231-9ddf-df24c698b8aa"],
        "thumbnail": "",
        "position": {"x": 238, "y": 217},
    },
    "1c2b956d-075b-5065-a439-b08b76ff34eb": {
        "key": "simcore/services/dynamic/raw-graphs",
        "version": "2.10.5",
        "label": "Post Processing",
        "inputs": {},
        "inputAccess": {
            "input_1": "Invisible",
            "input_2": "Invisible",
            "input_3": "Invisible",
            "input_4": "Invisible",
            "input_5": "Invisible",
        },
        "inputNodes": ["9ed12c45-0bd7-5acf-98ab-bf7568ee5da5"],
        "thumbnail": "",
        "position": {"x": 431, "y": 347},
    },
}


@app.put("/workbench")
async def update_workbench(project_uuid: UUID, workbench: Dict[str, Dict]):
    pass

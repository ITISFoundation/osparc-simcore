from typing import Dict, List

from faker import Faker

from ...models.schemas.solvers import TaskStates
from . import solvers_faker

fake = Faker()
opencor = solvers_faker.FAKE.solvers[0]
isolve_old = solvers_faker.FAKE.solvers[1]
isolve_latest = solvers_faker.FAKE.solvers[2]


class FAKE:
    user_jobs: List[Dict] = [
        # two jobs with one solver
        {
            "job_id": "a862c478-cca2-4675-9c44-6d12e01b419a",
            "inputs_sha": "11",
            "solver_id": opencor["uuid"],
        },
        {
            "job_id": "5952770d-44b8-4b04-80ee-9dd3f69a18a2",
            "inputs_sha": "22",
            "solver_id": opencor["uuid"],
        },
        # same input with two different versions of a solver
        {
            "job_id": "f718244c-9840-47fd-8140-e67c0d27f902",
            "inputs_sha": "33",
            "solver_id": isolve_old["uuid"],
        },
        {
            "job_id": "cf2440fa-730c-408b-82ba-ea1d417e1e08",
            "inputs_sha": "33",
            "solver_id": isolve_latest["uuid"],
        },
    ]

    job_states = {}

import csv
from pathlib import Path
from typing import Dict, List
import sys
from locust import HttpLocust, TaskSet, between, task
from uuid import uuid4
import random
from yarl import URL

# pylint: disable=attribute-defined-outside-init

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
data_dir = current_dir / ".."/"data"

def read_projects() -> List[Dict]:
    with open(data_dir / "projects.csv", 'rt') as fh:
        reader = csv.reader(fh)
        keys = next(reader)
        return [ dict( zip(keys, values) ) for values in reader ]

def get_url(project: Dict) -> URL:
    uuid = project['uuid']
    url = origin.with_path(f"/study/{uuid}")
    return url

origin = URL("http://127.0.0.1:9081")
projects = read_projects()

print(f"Loaded {len(projects)} projects for test...")
print(f"Target host: {origin}")


class UserBehaviour(TaskSet):
    def on_start(self):
        """ on_start is called when a Locust start before any task is scheduled """
        self._id = str(uuid4())
        self._prj = random.choice(projects)
        print(f"starting {self._id[:4]} -> {self._prj['name']}")

    def on_stop(self):
        """ on_stop is called when the TaskSet is stopping """
        print(f"stoping {self._id[:4]}")

    @task(1)
    def run_project(self):
        url = get_url(self._prj)
        print(f"Getting {url}")
        self.client.get(str(url))



class WebsiteUser(HttpLocust):
    task_set = UserBehaviour
    wait_time = between(5, 9)

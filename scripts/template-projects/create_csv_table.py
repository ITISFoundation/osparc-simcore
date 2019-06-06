import json

from change_case import ChangeCase

from simcore_service_webserver.projects.projects_models import ProjectType, projects
from simcore_service_webserver.resources import resources

TEMPLATE_STUDIES_NAME = 'data/fake-template-projects.isan.json'
TEMPLATE_STUDIES_TABLE = "template-projects-table.csv"

COLS = [c.name for c in projects.columns if c!=projects.c.id] #pylint: disable=not-an-iterable
PROJECT_KEYS = [ChangeCase.snake_to_camel(key) for key in COLS]
ROW = ",".join( ["{}", ]*len(PROJECT_KEYS) )

def normalize(key, value):
    if key == "type":
        return ProjectType.TEMPLATE.name

    if value is None:
        return '""'

    value = str(value)
    value = value.replace("'", '"')
    value = value.replace('"', '""')
    value = '"' + value + '"'
    return value



def main():
    with resources.stream(TEMPLATE_STUDIES_NAME) as fp:
        data = json.load(fp)

    with open(TEMPLATE_STUDIES_TABLE, 'wt') as fh:
        print(",".join(COLS), file=fh)
        for project in data:
            values = [normalize(key, project.get(key)) for key in PROJECT_KEYS]
            print(ROW.format(*values), file=fh)

if __name__ == "__main__":
    main()

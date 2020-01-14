import csv
import json
import sys
from pathlib import Path
from typing import Dict, List

from simcore_service_webserver.projects.projects_db import \
    _convert_to_schema_names

SEPARATOR=','

current_file = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
current_dir = current_file.parent

def load_csv(csv_filepath: Path) -> List[Dict]:
    headers, items = [], []
    with open(csv_filepath, mode='r', encoding='utf-8-sig') as fhandler:
        reader = csv.reader(fhandler, delimiter=',', quotechar='"')
        for row in reader:
            if row:
                if not headers:
                    headers = row
                else:
                    item = { key: row[i] for i, key in enumerate(headers) }
                    items.append(item)
    return items


def load_projects(csv_path:Path ):
    """ Returns schema-compatible projects

    """
    db_projects = load_csv(csv_path)
    _projects = []

    # process
    for db_prj in db_projects:
        if int(db_prj.get('published', 0) or 0)==1:
            prj = _convert_to_schema_names(db_prj)

            # jsonifies
            dump = prj['workbench']
            # TODO: use Encoder instead?
            dump = dump.replace("False", 'false') \
                .replace("True", 'true') \
                .replace("None", 'null')
            try:
                prj['workbench'] = json.loads(dump)
            except json.decoder.JSONDecodeError as err:
                print(err)

            # TODO: validate against project schema!!

            _projects.append(prj)
        else:
            print("skipping {}".format(db_prj['name']))

    return _projects


def main():
    """
        Converts csv exported from db into project schema-compatible json files
    """
    for db_csv_export in current_dir.glob("template*.csv"):
        data_projects = load_projects(db_csv_export)
        json_path = db_csv_export.with_suffix('.json')
        with open(json_path, 'w') as fh:
            json.dump(data_projects, fh, indent=2)


if __name__ == "__main__":
    main()

import os
import tempfile
import typing
from pathlib import Path

from blackfynn import Blackfynn
from blackfynn.models import Collection

import utils
from simcore_service_storage.datcore import DatcoreClient
from simcore_service_storage.models import FileMetaData

dir_path = os.path.dirname(os.path.realpath(__file__))
api_token = os.environ.get("BF_API_KEY")
api_secret = os.environ.get("BF_API_SECRET")


if utils.has_datcore_tokens():
    client = DatcoreClient(api_token=api_token, api_secret=api_secret)
    api_secret = os.environ.get("BF_API_SECRET", "none")
    destination = str(Path("MaG/level1/level2"))
    fd, path = tempfile.mkstemp()

    try:
        with os.fdopen(fd, "w") as tmp:
            # do stuff with temp file
            tmp.write("stuff")

        f = client.upload_file(destination, path)
        f = client.delete_file(destination, Path(path).name)
    finally:
        os.remove(path)

    files = []
    if True:
        dataset = client.get_dataset("mag")
        # dataset.print_tree()
        client.list_dataset_files_recursively(files, dataset, Path(dataset.name))
    else:
        files = client.list_files_recursively()

    fd, path = tempfile.mkstemp()

    try:
        with os.fdopen(fd, "w") as tmp:
            # do stuff with temp file
            tmp.write("stuff")

        print(fd, path)
        destination_path = Path("mag/level1/level2/bla.txt")
        parts = destination_path.parts
        assert len(parts) > 1
        dataset_name = parts[0]
        object_path = Path(*parts[1:])
        file_name = object_path.name
        collections = list(object_path.parent.parts)
        destination = client.get_dataset(dataset_name)

        # check if dataset exists
        def _get_collection_id(folder, _collections, collection_id):
            if not len(_collections):
                return collection_id

            current = _collections.pop(0)
            for item in folder:
                if isinstance(item, Collection) and item.name == current:
                    collection_id = item.id
                    folder = item
                    break

            return _get_collection_id(folder, _collections, collection_id)

        my_id = ""
        my_id = _get_collection_id(destination, collections, my_id)
        package = client.client.get(my_id)
        client.upload_file(package, path)
        print(my_id)

    finally:
        os.remove(path)

import os
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

    files =  []
    if True:
        dataset = client.get_dataset("simcore-testing")
        client.list_dataset_files_recursively(files, dataset, Path(dataset.name))
    else:
        files = client.list_files_recursively()

    for f in files:
        print(f)

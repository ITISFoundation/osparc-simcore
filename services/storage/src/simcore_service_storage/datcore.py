""" Python2 Datcore client wrapper for simcore

    requires Blackfynn, check Makefile env2

"""
# FIXME: refactor!!!
# pylint: skip-file

import logging
import os
import urllib
from contextlib import suppress
from pathlib import Path
from typing import List, Union

from blackfynn import Blackfynn
from blackfynn.models import BaseCollection, Collection, DataPackage, Dataset

from simcore_service_storage.models import DatasetMetaData, FileMetaData, FileMetaDataEx
from simcore_service_storage.settings import DATCORE_ID, DATCORE_STR

logger = logging.getLogger(__name__)

DatasetMetaDataVec = List[DatasetMetaData]


def _get_collection_id(
    folder: BaseCollection, _collections: List[str], collection_id: str
) -> str:
    if not len(_collections):
        return collection_id

    current = _collections.pop(0)
    found = False
    for item in folder:
        if isinstance(item, Collection) and item.name == current:
            collection_id = item.id
            folder = item
            found = True
            break

    if found:
        return _get_collection_id(folder, _collections, collection_id)

    return ""


class DatcoreClient(object):
    def __init__(self, api_token=None, api_secret=None, host=None, streaming_host=None):
        # WARNING: contruction raise exception if service is not available.
        # Use datacore_wrapper for safe calls
        # TODO: can use https://developer.blackfynn.io/python/latest/configuration.html#environment-variables
        self._bf = Blackfynn(
            profile=None,
            api_token=api_token,
            api_secret=api_secret,
            host=host,
            streaming_host=streaming_host,
        )

    def profile(self):
        """
        Returns profile of current User
        """
        return self._bf.profile

    def _collection_from_destination(self, destination: str):
        destination_path = Path(destination)
        parts = destination_path.parts

        dataset_name = parts[0]
        dataset = self.get_dataset(dataset_name)
        if dataset is None:
            return None, None

        collection_id = dataset.id
        collection = dataset
        collections = []
        if len(parts) > 1:
            object_path = Path(*parts[1:])
            collections = list(object_path.parts)
            collection_id = ""
            collection_id = _get_collection_id(dataset, collections, collection_id)
            collection = self._bf.get(collection_id)

        return collection, collection_id

    def _destination_from_id(self, destination_id: str):
        # NOTE: .get(*) logs
        #  INFO:blackfynn.client.Blackfynn:Unable to retrieve object
        # if destination_id refers to a Dataset

        destination: Union[DataPackage, Collection] = self._bf.get(destination_id)
        if destination is None:
            destination: Dataset = self._bf.get_dataset(destination_id)

        return destination

    def list_files_recursively(self, dataset_filter: str = ""):
        files = []

        for dataset in self._bf.datasets():
            if not dataset_filter or dataset_filter in dataset.name:
                self.list_dataset_files_recursively(files, dataset, Path(dataset.name))

        return files

    def list_files_raw_dataset(self, dataset_id: str) -> List[FileMetaDataEx]:
        files = []  # raw packages
        _files = []  # fmds
        data = {}  # map to keep track of parents-child

        cursor = ""
        page_size = 1000
        api = self._bf._api.datasets

        dataset = self._bf.get_dataset(dataset_id)
        if dataset is not None:
            while True:
                resp = api._get(
                    api._uri(
                        "/{id}/packages?cursor={cursor}&pageSize={pageSize}&includeSourceFiles={includeSourceFiles}",
                        id=dataset_id,
                        cursor=cursor,
                        pageSize=page_size,
                        includeSourceFiles=False,
                    )
                )
                for package in resp.get("packages", list()):
                    id = package["content"]["id"]
                    data[id] = package
                    files.append(package)
                cursor = resp.get("cursor")
                if cursor is None:
                    break

            for f in files:
                if f["content"]["packageType"] != "Collection":
                    filename = f["content"]["name"]
                    file_path = ""
                    file_id = f["content"]["nodeId"]
                    _f = f
                    while "parentId" in _f["content"].keys():
                        parentid = _f["content"]["parentId"]
                        _f = data[parentid]
                        file_path = _f["content"]["name"] + "/" + file_path

                    bucket_name = dataset.name
                    file_name = filename
                    file_size = 0
                    object_name = str(Path(file_path) / file_name)

                    file_uuid = str(Path(bucket_name) / object_name)
                    created_at = f["content"]["createdAt"]
                    last_modified = f["content"]["updatedAt"]
                    parent_id = dataset_id
                    if "parentId" in f["content"]:
                        parentId = f["content"]["parentId"]
                        parent_id = data[parentId]["content"]["nodeId"]

                    fmd = FileMetaData(
                        bucket_name=bucket_name,
                        file_name=file_name,
                        object_name=object_name,
                        location=DATCORE_STR,
                        location_id=DATCORE_ID,
                        file_uuid=file_uuid,
                        file_id=file_id,
                        raw_file_path=file_uuid,
                        display_file_path=file_uuid,
                        created_at=created_at,
                        last_modified=last_modified,
                        file_size=file_size,
                    )
                    fmdx = FileMetaDataEx(fmd=fmd, parent_id=parent_id)
                    _files.append(fmdx)

        return _files

    def list_files_raw(self, dataset_filter: str = "") -> List[FileMetaDataEx]:
        _files = []

        for dataset in self._bf.datasets():
            _files = _files + self.list_files_raw_dataset(dataset.id)

        return _files

    def list_dataset_files_recursively(
        self, files: List[FileMetaData], base: BaseCollection, current_root: Path
    ):
        for item in base:
            if isinstance(item, Collection):
                _current_root = current_root / Path(item.name)
                self.list_dataset_files_recursively(files, item, _current_root)
            else:
                parts = current_root.parts
                bucket_name = parts[0]
                file_name = item.name
                file_size = 0
                # lets assume we have only one file
                if item.files:
                    file_name = Path(item.files[0].as_dict()["content"]["s3key"]).name
                    file_size = item.files[0].as_dict()["content"]["size"]
                # if this is in the root directory, the object_name is the filename only
                if len(parts) > 1:
                    object_name = str(Path(*list(parts)[1:]) / Path(file_name))
                else:
                    object_name = str(Path(file_name))

                file_uuid = str(Path(bucket_name) / Path(object_name))
                file_id = item.id
                created_at = item.created_at
                last_modified = item.updated_at
                fmd = FileMetaData(
                    bucket_name=bucket_name,
                    file_name=file_name,
                    object_name=object_name,
                    location=DATCORE_STR,
                    location_id=DATCORE_ID,
                    file_uuid=file_uuid,
                    file_id=file_id,
                    raw_file_path=file_uuid,
                    display_file_path=file_uuid,
                    created_at=created_at,
                    last_modified=last_modified,
                    file_size=file_size,
                )
                files.append(fmd)

    def create_dataset(self, ds_name, *, force_delete=False):
        """
        Creates a new dataset for the current user and returns it. Returns existing one
        if there is already a dataset with the given name.

        Args:
            ds_name (str): Name for the dataset (_,-,' ' and capitalization are ignored)
            force_delete (bool, optional): Delete first if dataset already exists
        """
        ds = None
        with suppress(Exception):
            ds = self._bf.get_dataset(ds_name)
            if force_delete:
                ds.delete()
                ds = None

        if ds is None:
            ds = self._bf.create_dataset(ds_name)

        return ds

    def get_dataset(self, ds_name, create_if_not_exists=False):
        """
        Returns dataset with the given name. Creates it if required.

        Args:
            ds_name (str): Name for the dataset
            create_if_not_exists (bool, optional): Create first if dataset already exists
        """

        ds = None
        with suppress(Exception):
            ds = self._bf.get_dataset(ds_name)

        if ds is None and create_if_not_exists:
            ds = self._bf.create_dataset(ds_name)

        return ds

    def delete_dataset(self, ds_name):
        """
        Deletes dataset with the given name.

        Args:
            ds_name (str): Name for the dataset
        """

        # this is not supported
        ds = self.get_dataset(ds_name)
        if ds is not None:
            self._bf.delete(ds.id)

    def exists_dataset(self, ds_name):
        """
        Returns True if dataset with the given name exists.

        Args:
            ds_name (str): Name for the dataset
        """

        ds = self.get_dataset(ds_name)
        return ds is not None

    def upload_file(self, destination: str, filepath: str, meta_data=None) -> bool:
        """
        Uploads a file to a given dataset/collection given its filepath on the host. Optionally
        adds some meta data

        Args:
            dataset (dataset): The dataset into whioch the file shall be uploaded
            filepath (path): Full path to the file
            meta_data (dict, optional): Dictionary of meta data

        Note:
            Blackfynn postprocesses data based on filendings. If it can do that
            the filenames on the server change.
        """
        # parse the destination and try to find the package_id to upload to
        collection, collection_id = self._collection_from_destination(destination)

        if collection is None:
            return False

        files = [
            filepath,
        ]
        self._bf._api.io.upload_files(
            collection, files, display_progress=True, use_agent=False
        )
        collection.update()

        if meta_data is not None:
            for f in files:
                filename = os.path.basename(f)
                package = self.get_package(collection, filename)
                if package is not None:
                    self._update_meta_data(package, meta_data)

        return True

    def _update_meta_data(self, package, meta_data):
        """
        Updates or replaces metadata for a package

        Args:
            package (package): The package for which the meta data needs update
            meta_data (dict): Dictionary of meta data
        """

        for key in meta_data.keys():
            package.set_property(key, meta_data[key], category="simcore")

        package.update()

    def download_file(self, source, filename, destination_path):
        """
        Downloads a frile from a source dataset/collection given its filename. Stores
        it under destination_path

        Args:
            source (dataset/collection): The dataset or collection to donwload from
            filename (str): Name of the file
            destination__apth (str): Path on host for storing file
        """

        url = self.download_link(source, filename)
        if url:
            _file = urllib.URLopener()  # nosec
            _file.retrieve(url, destination_path)
            return True
        return False

    def download_link(self, destination, filename):
        """
            returns presigned url for download, destination is a dataset or collection
        """
        collection, collection_id = self._collection_from_destination(destination)

        for item in collection:
            if isinstance(item, DataPackage):
                if Path(item.files[0].as_dict()["content"]["s3key"]).name == filename:
                    file_desc = self._bf._api.packages.get_sources(item.id)[0]
                    url = self._bf._api.packages.get_presigned_url_for_file(
                        item.id, file_desc.id
                    )
                    return url

        return ""

    def download_link_by_id(self, file_id):
        """
            returns presigned url for download of a file given its file_id
        """
        url = ""
        filename = ""
        package = self._bf.get(file_id)
        if package is not None:
            filename = Path(package.files[0].as_dict()["content"]["s3key"]).name

        file_desc = self._bf._api.packages.get_sources(file_id)[0]
        url = self._bf._api.packages.get_presigned_url_for_file(file_id, file_desc.id)

        return url, filename

    def get_package(self, source, filename):
        """
        Returns package from source by name if exists

        Args:
            source (dataset/collection): The dataset or collection to donwload from
            filename (str): Name of the file
        """

        source.update()
        for item in source:
            if item.name == filename:
                return item

        return None

    def delete_file(self, destination, filename):
        """
        Deletes file by name from destination by name

        Args:
            destination (dataset/collection): The dataset or collection to delete from
            filename (str): Name of the file
        """
        collection, collection_id = self._collection_from_destination(destination)

        if collection is None:
            return False

        collection.update()
        for item in collection:
            if isinstance(item, DataPackage):
                if Path(item.files[0].as_dict()["content"]["s3key"]).name == filename:
                    self._bf.delete(item)
                    return True

        return False

    def delete_file_by_id(self, id: str) -> bool:
        """
        Deletes file by id

        Args:
            datcore id for the file
        """
        package: DataPackage = self._bf.get(id)
        package.delete()
        return not package.exists

    def delete_files(self, destination):
        """
        Deletes all files in destination

        Args:
            destination (dataset/collection): The dataset or collection to delete
        """

        collection, collection_id = self._collection_from_destination(destination)

        if collection is None:
            return False

        collection.update()
        for item in collection:
            self._bf.delete(item)

    def update_meta_data(self, dataset, filename, meta_data):
        """
        Updates metadata for a file

        Args:
            dataset (package): Which dataset
            filename (str): Which file
            meta_data (dict): Dictionary of meta data
        """

        filename = os.path.basename(filename)
        package = self.get_package(dataset, filename)
        if package is not None:
            self._update_meta_data(package, meta_data)

    def get_meta_data(self, dataset, filename):
        """
        Returns metadata for a file

        Args:
            dataset (package): Which dataset
            filename (str): Which file
        """

        meta_data = {}
        filename = os.path.basename(filename)
        package = self.get_package(dataset, filename)
        if package is not None:
            meta_list = package.properties
            for m in meta_list:
                meta_data[m.key] = m.value

        return meta_data

    def delete_meta_data(self, dataset, filename, keys=None):
        """
        Deletes specified keys in meta data for source/filename.

        Args:
            dataset (package): Which dataset
            filename (str): Which file
            keys (list of str, optional): Deletes specified keys, deletes
            all meta data if None
        """

        filename = os.path.basename(filename)
        package = self.get_package(dataset, filename)
        if package is not None:
            if keys is None:
                for p in package.properties:
                    package.remove_property(p.key, category="simcore")
            else:
                for k in keys:
                    package.remove_property(k, category="simcore")

    def search(self, what, max_count):
        """
        Seraches a thing in the database. Returns max_count results

        Args:
            what (str): query
            max_count (int): Max number of results to return
        """
        return self._bf.search(what, max_count)

    def upload_file_to_id(self, destination_id: str, filepath: str):
        """
        Uploads file to a given dataset/collection by id given its filepath on the host
        adds some meta data.

        Returns the id for the newly created resource

        Note: filepath could be an array

        Args:
            destination_id : The dataset/collection id into which the file shall be uploaded
            filepath (path): Full path to the file
        """
        _id = ""
        destination = self._destination_from_id(destination_id)
        if destination is None:
            return _id

        files = [
            filepath,
        ]

        try:
            # TODO: PC->MAG: should protected API
            # TODO: add new agent SEE https://developer.blackfynn.io/python/latest/CHANGELOG.html#id31
            result = self._bf._api.io.upload_files(
                destination, files, display_progress=True, use_agent=False
            )
            if result and result[0] and "package" in result[0][0]:
                _id = result[0][0]["package"]["content"]["id"]

        except Exception:
            logger.exception("Error uploading file to datcore")

        return _id

    def create_collection(self, destination_id: str, collection_name: str):
        """
        Create a empty collection within destination
        Args:
            destination_id : The dataset/collection id into which the file shall be uploaded
            filepath (path): Full path to the file
        """
        destination = self._destination_from_id(destination_id)
        _id = ""

        if destination is None:
            return _id

        new_collection = Collection(collection_name)
        destination.add(new_collection)
        new_collection.update()
        destination.update()
        _id = new_collection.id

        return _id

    def list_datasets(self) -> DatasetMetaDataVec:
        data = []
        for dataset in self._bf.datasets():
            dmd = DatasetMetaData(dataset_id=dataset.id, display_name=dataset.name)
            data.append(dmd)

        return data

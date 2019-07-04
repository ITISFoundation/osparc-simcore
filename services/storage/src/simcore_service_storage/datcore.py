""" Python2 Datcore client wrapper for simcore

    requires Blackfynn, check Makefile env2

"""
# pylint: skip-file
import os
import urllib
from pathlib import Path
from typing import List

from blackfynn import Blackfynn
from blackfynn.models import BaseCollection, Collection, DataPackage

from simcore_service_storage.models import FileMetaData
from simcore_service_storage.settings import DATCORE_ID, DATCORE_STR

#FIXME: W0611:Unused IOAPI imported from blackfynn.api.transfers
#from blackfynn.api.transfers import IOAPI


#FIXME: W0212:Access to a protected member _api of a client class
# pylint: disable=W0212

class DatcoreClient(object):
    def __init__(self, api_token=None, api_secret=None, host=None, streaming_host=None):
        self.client = Blackfynn(profile=None, api_token=api_token, api_secret=api_secret,
                                host=host, streaming_host=streaming_host)
    def _context(self):
        """
        Returns current organizational context
        """
        return self.client.context

    def profile(self):
        """
        Returns profile of current User
        """
        return self.client.profile

    def organization(self):
        """
        Returns organization name
        """
        return self.client.context.name

    def list_datasets(self):
        ds = []
        for item in self.client.datasets():
            ds.append(item.name)

        return ds

    def list_files_recursively(self):
        files = []
        for dataset in self.client.datasets():
            self.list_dataset_files_recursively(files, dataset, Path(dataset.name))

        return files

    def list_dataset_files_recursively(self, files: List[FileMetaData], base: BaseCollection, current_root: Path):
        for item in base:
            if isinstance(item, Collection):
                _current_root = current_root  / Path(item.name)
                self.list_dataset_files_recursively(files, item, _current_root)
            else:
                parts = current_root.parts
                bucket_name = parts[0]
                file_name = item.name
                file_size = 0
                # lets assume we have only one file
                if item.files:
                    file_name = Path(item.files[0].as_dict()['content']['s3key']).name
                    file_size = item.files[0].as_dict()['content']['size']
                # if this is in the root directory, the object_name is the filename only
                if len(parts) > 1:
                    object_name = str(Path(*list(parts)[1:])/ Path(file_name))
                else:
                    object_name = str(Path(file_name))

                file_uuid = str(Path(bucket_name) / Path(object_name))
                file_id = item.id
                created_at = item.created_at
                last_modified = item.updated_at
                fmd = FileMetaData(bucket_name=bucket_name, file_name=file_name, object_name=object_name,
                        location=DATCORE_STR, location_id=DATCORE_ID, file_uuid=file_uuid, file_id=file_id,
                        raw_file_path=file_uuid, display_file_path=file_uuid, created_at=created_at,
                        last_modified=last_modified, file_size=file_size)
                files.append(fmd)


    def list_files(self, dataset: str =""):
        files = []
        if not dataset:
            for ds in self.client.datasets():
                for item in ds:
                    files.append(os.path.join(ds.name, item.name))
        else:
            ds = self.get_dataset(dataset)
            for item in ds:
                files.append(os.path.join(ds.name, item.name))

        return files

    def create_dataset(self, ds_name, force_delete=False):
        """
        Creates a new dataset for the current user and returns it. Returns existing one
        if there is already a dataset with the given name.

        Args:
            ds_name (str): Name for the dataset (_,-,' ' and capitalization are ignored)
            force_delete (bool, optional): Delete first if dataset already exists
        """

        ds = None
        try:
            ds = self.client.get_dataset(ds_name)
            if force_delete:
                ds.delete()
                ds = None
        except Exception: # pylint: disable=W0703
            pass

        if ds is None:
            ds = self.client.create_dataset(ds_name)

        return ds

    def get_dataset(self, ds_name, create_if_not_exists=False):
        """
        Returns dataset with the given name. Creates it if required.

        Args:
            ds_name (str): Name for the dataset
            create_if_not_exists (bool, optional): Create first if dataset already exists
        """

        ds = None
        try:
            ds = self.client.get_dataset(ds_name)
        except Exception: # pylint: disable=W0703
            pass

        if ds is None and create_if_not_exists:
            ds = self.client.create_dataset(ds_name)

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
            self.client.delete(ds.id)

    def exists_dataset(self, ds_name):
        """
        Returns True if dataset with the given name exists.

        Args:
            ds_name (str): Name for the dataset
        """

        ds = self.get_dataset(ds_name)
        return ds is not None

    def upload_file(self, dataset, filepath, meta_data = None):
        """
        Uploads a file to a given dataset given its filepath on the host. Optionally
        adds some meta data

        Args:
            dataset (dataset): The dataset into whioch the file shall be uploaded
            filepath (path): Full path to the file
            meta_data (dict, optional): Dictionary of meta data

        Note:
            Blackfynn postprocesses data based on filendings. If it can do that
            the filenames on the server change. This makes it difficult to retrieve
            them back by name (see get_sources below). Also, for now we assume we have
            only single file data.
        """



        files = [filepath]
        # pylint: disable = E1101
        self.client._api.io.upload_files(dataset, files, display_progress=True)
        dataset.update()

        if meta_data is not None:
            filename = os.path.basename(filepath)
            package = self.get_package(dataset, filename)
            if package is not None:
                self._update_meta_data(package, meta_data)

    def _update_meta_data(self, package, meta_data):
        """
        Updates or replaces metadata for a package

        Args:
            package (package): The package for which the meta data needs update
            meta_data (dict): Dictionary of meta data
        """

        for key in meta_data.keys():
            package.set_property(key, meta_data[key], category='simcore')

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

        # pylint: disable = E1101
        url = self.download_link(source, filename)
        if url:
            _file = urllib.URLopener()
            _file.retrieve(url, destination_path)
            return True
        return False

    def download_link(self, source, filename):
        """
            returns presigned url for download, source is a dataset
        """

        # pylint: disable = E1101
        for item in source:
            if Path(item.files[0].as_dict()['content']['s3key']).name == filename:
                file_desc = self.client._api.packages.get_sources(item.id)[0]
                url = self.client._api.packages.get_presigned_url_for_file(item.id, file_desc.id)
                return url

        return ""

    def exists_file(self, source, filename):
        """
        Checks if file exists in source

        Args:
            source (dataset/collection): The dataset or collection to donwload from
            filename (str): Name of the file
        """

        source.update()
        for item in source:
            if item.name == filename:
                return True

        return False

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

    def delete_file(self, source, filename):
        """
        Deletes file by name from source by name

        Args:
            source (dataset/collection): The dataset or collection to donwload from
            filename (str): Name of the file
        """
        source.update()
        for item in source:
            if Path(item.files[0].as_dict()['content']['s3key']).name == filename:
                self.client.delete(item)
                return

    def delete_file_by_id(self, id: str):
        """
        Deletes file by id

        Args:
            datcore id for the file
        """
        self.client.delete(id)

    def delete_files(self, source):
        """
        Deletes all files in source

        Args:
            source (dataset/collection): The dataset or collection to donwload from
        """

        source.update()
        for item in source:
            self.client.delete(item)

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
                    package.remove_property(p.key, category='simcore')
            else:
                for k in keys:
                    package.remove_property(k, category='simcore')

    def search(self, what, max_count):
        """
        Seraches a thing in the database. Returns max_count results

        Args:
            what (str): query
            max_count (int): Max number of results to return
        """
        return self.client.search(what, max_count)

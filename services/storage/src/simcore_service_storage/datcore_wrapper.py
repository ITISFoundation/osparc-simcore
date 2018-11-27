import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from functools import partial, wraps
from pathlib import Path
from textwrap import dedent
from typing import List

import attr
import execnet

from .models import FileMetaData
from .settings import DATCORE_ID, DATCORE_STR

FileMetaDataVec = List[FileMetaData]

CURRENT_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


#TODO: Use async callbacks for retreival of progress and pass via rabbit to server

def call_python_2(module, function, args, python_exec: Path):
    """ calls a module::function from python2 with the arguments list
    """
    # pylint: disable=E1101
    # "E1101:Module 'execnet' has no 'makegateway' member",
    gw = execnet.makegateway("popen//python=%s" % python_exec)
    channel = gw.remote_exec("""
        from %s import %s as the_function
        channel.send(the_function(*channel.receive()))
    """ % (module, function))
    channel.send(args)
    return channel.receive()

def call_python_2_script(script: str, python_exec: Path):
    """ calls an arbitrary script with remote interpreter

        MaG: I wonder how secure it is to pass the tokens that way...

    """
    prefix = "import sys\n" \
             "sys.path.append('%s')\n" % CURRENT_DIR
    script = prefix + dedent(script)

    # pylint: disable=E1101
    gw = execnet.makegateway("popen//python=%s" % python_exec)
    channel = gw.remote_exec(script)
    return channel.receive()

def make_async(func):
    @wraps(func)
    async def async_wrapper(self, *args, **kwargs):
        blocking_task = self.loop.run_in_executor(self.pool, func, self, *args, **kwargs)
        _completed, _pending = await asyncio.wait([blocking_task])
        results = [t.result() for t in _completed]
        # TODO: does this always work?
        return results[0]
    return async_wrapper

class DatcoreWrapper:
    """ Wrapper to call the python2 api from datcore

        Assumes that python 2 is installed in a virtual env

    """
    # pylint: disable=R0913
    # Too many arguments
    def __init__(self, api_token: str, api_secret: str, python2_exec: Path, loop: object, pool: ThreadPoolExecutor):
        self.api_token = api_token
        self.api_secret = api_secret

        self.loop = loop
        self.pool = pool
        #TODO: guarantee that python2_exec is a valid
        self._py2_call = partial(call_python_2_script, python_exec=python2_exec)


    @make_async
    def list_files(self, regex = "", sortby = "")->FileMetaDataVec: #pylint: disable=W0613
        # FIXME: W0613:Unused argument 'regex', sortby!!!
        script = """
            from datcore import DatcoreClient
            try:
                api_token = "%s"
                api_secret = "%s"

                d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                    host='https://api.blackfynn.io')

                files = d_client.list_files()

                channel.send(files)
            except Exception as e:
                channel.send([])

            """%(self.api_token, self.api_secret)


        files = self._py2_call(script)

        data = []
        for f in files:
            # extract bucket name, object name and filename
            parts = f.strip("/").split("/")
            file_name = parts[-1]
            if len(parts) > 1:
                bucket_name = parts[0]
                object_name = "/".join(parts[1:])
            else:
                bucket_name = ""
                object_name = file_name

            file_uuid = os.path.join(bucket_name, object_name)
            # at the moment, no metadata there
            fmd = FileMetaData(bucket_name=bucket_name, file_name=file_name, object_name=object_name,
             location=DATCORE_STR, location_id=DATCORE_ID, file_uuid=file_uuid)
            data.append(fmd)

        return data

    @make_async
    def delete_file(self, dataset: str, filename: str):
        # the object can be found in dataset/filename <-> bucket_name/object_name
        script = """
            from datcore import DatcoreClient

            api_token = "{0}"
            api_secret = "{1}"
            try:
                d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                    host='https://api.blackfynn.io')

                ds = d_client.get_dataset("{2}")
                if ds is not None:
                    d_client.delete_file(ds, "{3}")

                channel.send(True)

            except Exception as e:
                channel.send(False)
            """.format(self.api_token, self.api_secret, dataset, filename)

        return self._py2_call(script)

    @make_async
    def download_link(self, dataset: str, filename: str):
        script = """
            from datcore import DatcoreClient

            api_token = "{0}"
            api_secret = "{1}"
            try:
                d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                    host='https://api.blackfynn.io')

                ds = d_client.get_dataset("{2}")
                url = ""
                if ds is not None:
                    url = d_client.download_link(ds, "{3}")

                channel.send(url)

            except Exception as e:
                channel.send("")
            """.format(self.api_token, self.api_secret, dataset, filename)

        return self._py2_call(script)

    @make_async
    def create_test_dataset(self, dataset):
        script = """
            from datcore import DatcoreClient

            api_token = "{0}"
            api_secret = "{1}"
            try:
                d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                    host='https://api.blackfynn.io')

                ds = d_client.get_dataset("{2}")
                if ds is not None:
                    d_client.delete_files(ds)
                else:
                    d_client.create_dataset("{2}")

                channel.send(None)
            except Exception as e:
                channel.send(False)
            """.format(self.api_token, self.api_secret, dataset)

        return self._py2_call(script)

    @make_async
    def delete_test_dataset(self, dataset):
        script = """
            from datcore import DatcoreClient

            api_token = "{0}"
            api_secret = "{1}"
            try:
                d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                    host='https://api.blackfynn.io')

                ds = d_client.get_dataset("{2}")
                if ds is not None:
                    d_client.delete_files(ds)

                channel.send(True)
            except Exception as e:
                channel.send(False)

            """.format(self.api_token, self.api_secret, dataset)

        return self._py2_call(script)

    @make_async
    def upload_file(self, dataset: str, local_path: str, meta_data: FileMetaData = None):
        json_meta = ""
        if meta_data:
            json_meta = json.dumps(attr.asdict(meta_data))

        script = """
            from datcore import DatcoreClient
            import json

            api_token = "{0}"
            api_secret = "{1}"

            try:
                d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                    host='https://api.blackfynn.io')

                ds = d_client.get_dataset("{2}")

                str_meta = '{4}'
                if str_meta :
                    meta_data = json.loads(str_meta)
                    d_client.upload_file(ds, "{3}", meta_data)
                else:
                    d_client.upload_file(ds, "{3}")

                channel.send(True)

            except Exception as e:
                channel.send(False)

            """.format(self.api_token, self.api_secret, dataset, local_path, json_meta)

        return self._py2_call(script)

    @make_async
    def ping(self):
        script = """
            from datcore import DatcoreClient

            api_token = "{0}"
            api_secret = "{1}"

            try:
                d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                    host='https://api.blackfynn.io')

                profile = d_client.profile()
                ok = profile is not None
                channel.send(ok)

            except Exception as e:
                channel.send(False)

            """.format(self.api_token, self.api_secret)

        return self._py2_call(script)

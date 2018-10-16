import execnet
from functools import partial
from .models import FileMetaData
from pathlib import Path
from typing import List
from textwrap import dedent

FileMetaDataVec = List[FileMetaData]

CURRENT_DIR = Path(__file__).resolve().parent

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

class DatcoreWrapper:
    """ Wrapper to call the python2 api from datcore

        Assumes that python 2 is installed in a virtual env

    """
    def __init__(self, api_token: str, api_secret: str, python2_exec: Path):
        self.api_token = api_token
        self.api_secret = api_secret

        #TODO: guarantee that python2_exec is a valid
        self._py2_call = partial(call_python_2_script, python_exec=python2_exec)

    def list_files(self, regex = "", sortby = "")->FileMetaDataVec: #pylint: disable=W0613
        # FIXME: W0613:Unused argument 'regex', sortby!!!
        script = """
            from datcore import DatcoreClient

            api_token = "%s"
            api_secret = "%s"

            d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                host='https://api.blackfynn.io')

            files = d_client.list_files()

            channel.send(files)

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

            # at the moment, no metadata there
            fmd = FileMetaData(bucket_name=bucket_name, file_name=file_name, object_name=object_name)
            data.append(fmd)

        return data

    def delete_file(self, fmd):
        # the object can be found in dataset/filename <-> bucket_name/object_name
        dataset = fmd.bucket_name
        file_name = fmd.object_name

        script = """
            from datcore import DatcoreClient

            api_token = "{0}"
            api_secret = "{1}"

            d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                host='https://api.blackfynn.io')

            ds = d_client.get_dataset("{2}")
            if ds is not None:
                d_client.delete_file(ds, "{3}")

            channel.send(None)
            """.format(self.api_token, self.api_secret, dataset, file_name)

        return self._py2_call(script)

    def download_link(self, fmd):
        dataset = fmd.bucket_name
        file_name = fmd.object_name

        script = """
            from datcore import DatcoreClient

            api_token = "{0}"
            api_secret = "{1}"

            d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                host='https://api.blackfynn.io')

            ds = d_client.get_dataset("{2}")
            url = ""
            if ds is not None:
                url = d_client.download_link(ds, "{3}")

            channel.send(url)
            """.format(self.api_token, self.api_secret, dataset, file_name)

        return self._py2_call(script)

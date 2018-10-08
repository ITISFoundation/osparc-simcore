import execnet

from .models import FileMetaData

from typing import List
import os

FileMetaDataVec = List[FileMetaData]


def call_python_2(module, function, args):
    """ calls a module::function from python2 with the arguments list
    """
    # TODO: fix hardcoded path to the venv
    
    gw = execnet.makegateway("popen//python=/home/guidon/miniconda3/envs/py27/bin/python")
    channel = gw.remote_exec("""
        from %s import %s as the_function
        channel.send(the_function(*channel.receive()))
    """ % (module, function))
    channel.send(args)
    return channel.receive()

def call_python_2_script(script: str):
    """ calls an arbitrary script with remote interpreter
        
        MaG: I wonder how secure it is to pass the tokens that way...

    """
    gw = execnet.makegateway("popen//python=/home/guidon/miniconda3/envs/py27/bin/python")
    channel = gw.remote_exec(script)
    return channel.receive()

class DatcoreWrapper(object):
    """ Wrapper to call the python2 api from datcore

        Assumes that python 2 is installed in a virtual env

    """
    def __init__(self, api_token, api_secret):
        self.api_token = api_token
        self.api_secret = api_secret
                        
    def list_files(self, regex = "", sortby = "")->FileMetaDataVec:
        script = """
            from datcore import DatcoreClient
            
            api_token = "%s"
            api_secret = "%s"

            d_client = DatcoreClient(api_token=api_token, api_secret=api_secret,
                host='https://api.blackfynn.io')
       
            files = d_client.list_files()

            channel.send(files)

            """%(self.api_token, self.api_secret)

        files = call_python_2_script(script)
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

        return call_python_2_script(script)

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

        return call_python_2_script(script)
      

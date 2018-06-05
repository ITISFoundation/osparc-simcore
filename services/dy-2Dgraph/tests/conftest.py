#pylint: disable C0111
"""defines fixtures for pytests."""

import pytest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "helpers"))


@pytest.fixture()
def default_simcore_configuration():
    """initialise simcore with default configuration file
    """

    import os
    default_config_path = os.path.join(os.path.dirname(
        os.path.realpath(__file__)), r"../config/connection_config.json")
    os.environ["SIMCORE_CONFIG_PATH"] = default_config_path    

@pytest.fixture()
def special_simcore_configuration(request):
    """allows for initialisation of simcore with custom configuration file.
    
    Arguments:
        request {internal pytest object} -- internal
    
    Returns:
        function -- function to call to set the alternative configuration as a dictionary
    """

    def create_special_config(configuration):
        """sets the special configuration to be used by simcore
        
        Arguments:
            configuration {dict} -- json configuration to be set
        
        Returns:
            string -- path to the temporary config file used. 
                        The file is automatically deleted.
        """

        import os
        import json
        import tempfile
        # create temporary json file
        temp_file = tempfile.NamedTemporaryFile()
        temp_file.close()
        # ensure the file is removed at the end whatever happens

        def fin():
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            assert not os.path.exists(temp_file.name)
        request.addfinalizer(fin)
        # get the configuration to set up
        config = configuration
        assert config
        # create the special configuration file
        with open(temp_file.name, "w") as file_pointer:
            json.dump(config, file_pointer)
        assert os.path.exists(temp_file.name)
        # set the environment variable such that simcore will use the special file
        os.environ["SIMCORE_CONFIG_PATH"] = temp_file.name
        return temp_file.name
    return create_special_config
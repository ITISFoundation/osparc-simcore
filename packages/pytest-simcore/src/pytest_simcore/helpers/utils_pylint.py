""" Helps with running Pylint tests on different modules """
import subprocess


def assert_pylint_is_passing(pylintrc, package_dir, autodetect=0):
    """Runs Pylint with given inputs. In case of error some helpful Pylint messages are displayed

    This is used in different packages
    """
    cmd = f"pylint --jobs={autodetect} --rcfile {pylintrc} -v {package_dir}".split(" ")
    pipes = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    std_out, _ = pipes.communicate()
    if pipes.returncode != 0:
        print(std_out.decode("utf-8"))
        assert False, "Pylint failed with error, check this test's stdout to fix it"

""" Helps with running Pylint tests on different modules """
import subprocess


AUTODETECT = 0


def assert_pylint_is_passing(pylintrc, package_dir, number_of_jobs: int = AUTODETECT):
    """Runs Pylint with given inputs. In case of error some helpful Pylint messages are displayed

    This is used in different packages
    """
    command = f"pylint --jobs={number_of_jobs} --rcfile {pylintrc} -v {package_dir}".split(
        " "
    )
    pipes = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    std_out, _ = pipes.communicate()
    if pipes.returncode != 0:
        print(f'>>>> Exit code "{pipes.returncode}"\n{std_out.decode("utf-8")}\n<<<<')
        assert False, "Pylint failed with error, check this test's stdout to fix it"

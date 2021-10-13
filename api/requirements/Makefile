#
# Targets to pip-compile requirements
#
include ../../requirements/base.Makefile

# Add here any extra explicit dependency: e.g. _migration.txt: _base.txt

_test.txt: _test.in

_tools.txt: _tools.in _test.txt $(REPO_BASE_DIR)/requirements/devenv.txt

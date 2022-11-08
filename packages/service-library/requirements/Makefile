#
# Targets to pip-compile requirements
#
include ../../../requirements/base.Makefile

# Add here any extra explicit dependency: e.g. _migration.txt: _base.txt
_aiohttp.txt: _base.txt
_fastapi.txt: _base.txt
_test.in: _aiohttp.txt _fastapi.txt _base.txt

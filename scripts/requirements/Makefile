# Recipes to upgrade requirements
#
# USE CAREFULLY. UNDER DEVELOPMENT
#
#
#  Examples
#
#  - To upgrade only a package:
#    make all upgrade=psycopg2-binary
#

ROOTDIR = $(abspath $(CURDIR)/../..)
UPGRADE_OPTION:= $(if $(upgrade),--upgrade-package $(upgrade),)

inputs := $(shell grep --include=*.in --recursive --files-with-match $(upgrade) $(ROOTDIR))
outputs := $(inputs:.in=.txt)


.DEFAULT_TARGET=info


%.txt: %.in
	export CUSTOM_COMPILE_COMMAND='make $(notdir $@)'; pip-compile --annotate $(UPGRADE_OPTION) --output-file $@ $<


.PHONY: touch
touch:
	$(foreach p,$(inputs),touch $(p);)

.PHONY: all
all: touch $(outputs)


.PHONY: info
info:
	# $(inputs)
	# ---------
	# $(outputs)

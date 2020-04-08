# Recipes to upgrade requirements in batch
#
# USE CAREFULLY. UNDER DEVELOPMENT
#


# locations
ROOTDIR := $(abspath $(CURDIR)/../..)
PACKAGES_DIR := $(abspath $(ROOTDIR)/packages)

# tools
MAKE_C := $(MAKE) --no-print-directory --directory

# flags
UPGRADE_OPTION:= $(if $(upgrade),--upgrade-package $(upgrade),)


.PHONY: touch packages
_base-in-reqs := $(shell find packages -type f -name _base.in)

touch:
	$(foreach p,${_base-in-reqs},touch $(p);)

packages:
	$(foreach p,${_base-in-reqs},touch $(p); $(MAKE_C) $(dir $(p)) reqs;)

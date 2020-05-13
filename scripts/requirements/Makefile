# Recipes to upgrade requirements in batch
#
# Examples of usage
#
# - Full upgrade of all packages
#  	make touch packages
#
# - Upgrade one library in all packages
#   make packages upgrade=name-of-package
#
#
# WARNING: USE CAREFULLY. STILL UNDER DEVELOPMENT
#


# locations
ROOTDIR := $(abspath $(CURDIR)/../..)
PACKAGES_DIR := $(abspath $(ROOTDIR)/packages)

# tools
MAKE_C := $(MAKE) --no-print-directory --directory


.PHONY: touch packages
_base-in-reqs := $(shell find ${PACKAGES_DIR} -type f -name _base.in)

touch:
	$(foreach p,${_base-in-reqs},touch $(p);)

packages:
	$(foreach p,${_base-in-reqs},touch $(p); $(MAKE_C) $(dir $(p)) reqs $(upgrade);)

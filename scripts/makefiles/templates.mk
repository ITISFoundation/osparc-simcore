# Shared recipe body to create files from template counterparts.
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
# SEE scripts/makefiles/README.md for conventions.

define clone_from_template
$(if $(wildcard $@), \
@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)
endef

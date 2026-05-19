# Shared recipe body to create files from template counterparts.

define clone_from_template
$(if $(wildcard $@), \
@echo "WARNING #####  $< is newer than $@ ####"; diff -uN $@ $<; false;,\
@echo "WARNING ##### $@ does not exist, cloning $< as $@ ############"; cp $< $@)
endef

include ../../scripts/common.Makefile


ifneq (,$(wildcard $(DOT_ENV_FILE)))
    include $(DOT_ENV_FILE)
    export $(shell sed 's/=.*//' $(DOT_ENV_FILE))
endif



scripts/%.sql: scripts/%.sql.template
	@echo "Generating SQL script from '$<'..."
	@envsubst < $< > $@
	@echo "SQL script generated as '$@'"

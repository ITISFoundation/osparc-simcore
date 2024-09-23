include ../../scripts/common.Makefile


ifneq (,$(wildcard $(DOT_ENV_FILE)))
    include $(DOT_ENV_FILE)
    export $(shell sed 's/=.*//' $(DOT_ENV_FILE))
endif


readonly_user=${POSTGRES_READONLY_USER}
readonly_password=${POSTGRES_READONLY_PASSWORD}
database=${POSTGRES_DB}
schema=$(if $(POSTGRES_SCHEMA),$(POSTGRES_SCHEMA),public)

.PHONY: readonly-user-sql
readonly-user-sql: ##  ql-script to create a new readonly user
	@echo " -- Creating read-only user ${readonly_user} for ${database}.${schema}"
	@echo
	@echo " --Create the read-only user with a password"
	@echo "CREATE USER \"${readonly_user}\" WITH PASSWORD '${readonly_password}';"
	@echo " --Grant CONNECT privilege to the database (e.g., 'foo' is the database name)"
	@echo "GRANT CONNECT ON DATABASE ${database} TO \"${readonly_user}\";"
	@echo " --Grant USAGE privilege on the public schema"
	@echo "GRANT USAGE ON SCHEMA ${schema} TO \"${readonly_user}\";"
	@echo " --Grant SELECT privilege on all existing tables in the public schema"
	@echo "GRANT SELECT ON ALL TABLES IN SCHEMA ${schema} TO \"${readonly_user}\";"
	@echo " --Grant SELECT privilege on all existing sequences in the public schema"
	@echo "GRANT SELECT ON ALL SEQUENCES IN SCHEMA ${schema} TO \"${readonly_user}\";"
	@echo " --Ensure that future tables created in the public schema will have SELECT privilege for the read-only user"
	@echo "ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema} GRANT SELECT ON TABLES TO \"${readonly_user}\";"
	@echo " --Ensure that future sequences created in the public schema will have SELECT privilege for the read-only user"
	@echo "ALTER DEFAULT PRIVILEGES IN SCHEMA ${schema} GRANT SELECT ON SEQUENCES TO \"${readonly_user}\";"
	@echo
	@echo " -- Listing all users"
	@echo "SELECT * FROM pg_roles;"

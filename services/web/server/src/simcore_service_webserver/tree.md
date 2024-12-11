This is a tree view of my app. It is built in python's aiohttp.


├── activity
│   ├── _api.py
│   ├── _handlers.py
│   ├── plugin.py
│   └── settings.py
├── announcements
│   ├── _api.py
│   ├── _handlers.py
│   ├── _models.py
│   ├── plugin.py
│   └── _redis.py
├── api_keys
│   ├── api.py
│   ├── errors.py
│   ├── _exceptions_handlers.py
│   ├── _models.py
│   ├── plugin.py
│   ├── _repository.py
│   ├── _rest.py
│   ├── _rpc.py
│   └── _service.py
├── application.py
├── application_settings.py
├── application_settings_utils.py
├── catalog
│   ├── _api.py
│   ├── _api_units.py
│   ├── client.py
│   ├── _constants.py
│   ├── exceptions.py
│   ├── _handlers_errors.py
│   ├── _handlers.py
│   ├── licenses
│   │   ├── api.py
│   │   ├── errors.py
│   │   ├── _exceptions_handlers.py
│   │   ├── _licensed_items_api.py
│   │   ├── _licensed_items_db.py
│   │   ├── _licensed_items_handlers.py
│   │   ├── _models.py
│   │   └── plugin.py
│   ├── _models.py
│   ├── plugin.py
│   ├── settings.py
│   └── _tags_handlers.py
├── cli.py
├── _constants.py
├── db
│   ├── _aiopg.py
│   ├── _asyncpg.py
│   ├── base_repository.py
│   ├── models.py
│   ├── plugin.py
│   └── settings.py
├── db_listener
│   ├── _db_comp_tasks_listening_task.py
│   ├── plugin.py
│   └── _utils.py
├── diagnostics
│   ├── _handlers.py
│   ├── _healthcheck.py
│   ├── _monitoring.py
│   ├── plugin.py
│   └── settings.py
├── director_v2
│   ├── _abc.py
│   ├── api.py
│   ├── _api_utils.py
│   ├── _core_base.py
│   ├── _core_computations.py
│   ├── _core_dynamic_services.py
│   ├── _core_utils.py
│   ├── exceptions.py
│   ├── _handlers.py
│   ├── plugin.py
│   └── settings.py
├── dynamic_scheduler
│   ├── api.py
│   ├── plugin.py
│   └── settings.py
├── email
│   ├── _core.py
│   ├── _handlers.py
│   ├── plugin.py
│   ├── settings.py
│   └── utils.py
├── errors.py
├── exception_handling
│   ├── _base.py
│   └── _factory.py
├── exporter
│   ├── exceptions.py
│   ├── _formatter
│   │   ├── archive.py
│   │   ├── _sds.py
│   │   ├── template_json.py
│   │   └── xlsx
│   │       ├── code_description.py
│   │       ├── core
│   │       │   ├── styling_components.py
│   │       │   └── xlsx_base.py
│   │       ├── dataset_description.py
│   │       ├── manifest.py
│   │       ├── utils.py
│   │       └── writer.py
│   ├── _handlers.py
│   ├── plugin.py
│   ├── settings.py
│   └── utils.py
├── folders
│   ├── api.py
│   ├── errors.py
│   ├── _exceptions_handlers.py
│   ├── _folders_api.py
│   ├── _folders_db.py
│   ├── _folders_handlers.py
│   ├── _models.py
│   ├── plugin.py
│   ├── _trash_api.py
│   ├── _trash_handlers.py
│   ├── _workspaces_api.py
│   └── _workspaces_handlers.py
├── garbage_collector
│   ├── _core_disconnected.py
│   ├── _core_guests.py
│   ├── _core_orphans.py
│   ├── _core.py
│   ├── _core_utils.py
│   ├── plugin.py
│   ├── settings.py
│   ├── _tasks_api_keys.py
│   ├── _tasks_core.py
│   ├── _tasks_trash.py
│   └── _tasks_users.py
├── groups
│   ├── api.py
│   ├── _classifiers_api.py
│   ├── _classifiers_handlers.py
│   ├── _common
│   │   ├── exceptions_handlers.py
│   │   └── schemas.py
│   ├── exceptions.py
│   ├── _groups_api.py
│   ├── _groups_db.py
│   ├── _groups_handlers.py
│   └── plugin.py
├── invitations
│   ├── api.py
│   ├── _client.py
│   ├── _core.py
│   ├── errors.py
│   ├── plugin.py
│   └── settings.py
├── login
│   ├── _2fa_api.py
│   ├── _2fa_handlers.py
│   ├── _auth_api.py
│   ├── _auth_handlers.py
│   ├── cli.py
│   ├── _confirmation.py
│   ├── _constants.py
│   ├── decorators.py
│   ├── errors.py
│   ├── handlers_change.py
│   ├── handlers_confirmation.py
│   ├── handlers_registration.py
│   ├── _models.py
│   ├── plugin.py
│   ├── _registration_api.py
│   ├── _registration_handlers.py
│   ├── _registration.py
│   ├── _security.py
│   ├── settings.py
│   ├── _sql.py
│   ├── storage.py
│   ├── utils_email.py
│   └── utils.py
├── log.py
├── long_running_tasks.py
├── __main__.py
├── meta_modeling
│   ├── _function_nodes.py
│   ├── _handlers.py
│   ├── _iterations.py
│   ├── plugin.py
│   ├── _projects.py
│   ├── _results.py
│   └── _version_control.py
├── _meta.py
├── models.py
├── notifications
│   ├── plugin.py
│   ├── project_logs.py
│   ├── _rabbitmq_consumers_common.py
│   ├── _rabbitmq_exclusive_queue_consumers.py
│   ├── _rabbitmq_nonexclusive_queue_consumers.py
│   └── wallet_osparc_credits.py
├── payments
│   ├── api.py
│   ├── _autorecharge_api.py
│   ├── _autorecharge_db.py
│   ├── errors.py
│   ├── _events.py
│   ├── _methods_api.py
│   ├── _methods_db.py
│   ├── _onetime_api.py
│   ├── _onetime_db.py
│   ├── plugin.py
│   ├── _rpc_invoice.py
│   ├── _rpc.py
│   ├── settings.py
│   ├── _socketio.py
│   └── _tasks.py
├── products
│   ├── _api.py
│   ├── api.py
│   ├── _db.py
│   ├── errors.py
│   ├── _events.py
│   ├── _handlers.py
│   ├── _invitations_handlers.py
│   ├── _middlewares.py
│   ├── _model.py
│   ├── plugin.py
│   └── _rpc.py
├── projects
│   ├── _access_rights_api.py
│   ├── _access_rights_db.py
│   ├── api.py
│   ├── _comments_api.py
│   ├── _comments_db.py
│   ├── _comments_handlers.py
│   ├── _common_models.py
│   ├── _crud_api_create.py
│   ├── _crud_api_delete.py
│   ├── _crud_api_read.py
│   ├── _crud_handlers_models.py
│   ├── _crud_handlers.py
│   ├── db.py
│   ├── _db_utils.py
│   ├── exceptions.py
│   ├── _folders_api.py
│   ├── _folders_db.py
│   ├── _folders_handlers.py
│   ├── _groups_api.py
│   ├── _groups_db.py
│   ├── _groups_handlers.py
│   ├── lock.py
│   ├── _metadata_api.py
│   ├── _metadata_db.py
│   ├── _metadata_handlers.py
│   ├── models.py
│   ├── _nodes_api.py
│   ├── _nodes_handlers.py
│   ├── _nodes_utils.py
│   ├── nodes_utils.py
│   ├── _observer.py
│   ├── _permalink_api.py
│   ├── plugin.py
│   ├── _ports_api.py
│   ├── _ports_handlers.py
│   ├── _projects_access.py
│   ├── projects_api.py
│   ├── _projects_db.py
│   ├── _projects_nodes_pricing_unit_handlers.py
│   ├── settings.py
│   ├── _states_handlers.py
│   ├── _tags_api.py
│   ├── _tags_handlers.py
│   ├── _trash_api.py
│   ├── _trash_handlers.py
│   ├── utils.py
│   ├── _wallets_api.py
│   ├── _wallets_handlers.py
│   ├── _workspaces_api.py
│   └── _workspaces_handlers.py
├── publications
│   ├── _handlers.py
│   └── plugin.py
├── rabbitmq.py
├── rabbitmq_settings.py
├── redis.py
├── resource_manager
│   ├── _constants.py
│   ├── plugin.py
│   ├── registry.py
│   ├── settings.py
│   └── user_sessions.py
├── _resources.py
├── resource_usage
│   ├── api.py
│   ├── _client.py
│   ├── _constants.py
│   ├── errors.py
│   ├── _observer.py
│   ├── plugin.pyf
│   ├── _pricing_plans_admin_api.py
│   ├── _pricing_plans_admin_handlers.py
│   ├── _pricing_plans_api.py
│   ├── _pricing_plans_handlers.py
│   ├── _service_runs_api.py
│   ├── _service_runs_handlers.py
│   ├── settings.py
│   └── _utils.py
├── rest
│   ├── _handlers.py
│   ├── healthcheck.py
│   ├── plugin.py
│   ├── settings.py
│   └── _utils.py
├── scicrunch
│   ├── db.py
│   ├── errors.py
│   ├── models.py
│   ├── plugin.py
│   ├── _resolver.py
│   ├── _rest.py
│   ├── service_client.py
│   └── settings.py
├── security
│   ├── api.py
│   ├── _authz_access_model.py
│   ├── _authz_access_roles.py
│   ├── _authz_db.py
│   ├── _authz_policy.py
│   ├── _constants.py
│   ├── decorators.py
│   ├── _identity_api.py
│   ├── _identity_policy.py
│   └── plugin.py
├── session
│   ├── access_policies.py
│   ├── api.py
│   ├── _cookie_storage.py
│   ├── errors.py
│   ├── plugin.py
│   └── settings.py
├── socketio
│   ├── _handlers.py
│   ├── messages.py
│   ├── models.py
│   ├── _observer.py
│   ├── plugin.py
│   ├── server.py
│   └── _utils.py
├── statics
│   ├── _constants.py
│   ├── _events.py
│   ├── _handlers.py
│   ├── plugin.py
│   └── settings.py
├── storage
│   ├── api.py
│   ├── _handlers.py
│   ├── plugin.py
│   ├── schemas.py
│   └── settings.py
├── studies_dispatcher
│   ├── _catalog.py
│   ├── _constants.py
│   ├── _core.py
│   ├── _errors.py
│   ├── _models.py
│   ├── plugin.py
│   ├── _projects_permalinks.py
│   ├── _projects.py
│   ├── _redirects_handlers.py
│   ├── _rest_handlers.py
│   ├── settings.py
│   ├── _studies_access.py
│   └── _users.py
├── tags
│   ├── _api.py
│   ├── _handlers.py
│   ├── plugin.py
│   └── schemas.py
├── tracing.py
├── users
│   ├── _api.py
│   ├── api.py
│   ├── _constants.py
│   ├── _db.py
│   ├── exceptions.py
│   ├── _handlers.py
│   ├── _models.py
│   ├── _notifications_handlers.py
│   ├── _notifications.py
│   ├── plugin.py
│   ├── _preferences_api.py
│   ├── preferences_api.py
│   ├── _preferences_db.py
│   ├── _preferences_handlers.py
│   ├── _preferences_models.py
│   ├── _schemas.py
│   ├── schemas.py
│   ├── settings.py
│   ├── _tokens_handlers.py
│   └── _tokens.py
├── utils_aiohttp.py
├── utils.py
├── utils_rate_limiting.py
├── version_control
│   ├── _core.py
│   ├── db.py
│   ├── errors.py
│   ├── _handlers_base.py
│   ├── _handlers.py
│   ├── models.py
│   ├── plugin.py
│   ├── vc_changes.py
│   └── vc_tags.py
├── wallets
│   ├── _api.py
│   ├── api.py
│   ├── _constants.py
│   ├── _db.py
│   ├── errors.py
│   ├── _events.py
│   ├── _groups_api.py
│   ├── _groups_db.py
│   ├── _groups_handlers.py
│   ├── _handlers.py
│   ├── _payments_handlers.py
│   └── plugin.py
└── workspaces
    ├── api.py
    ├── errors.py
    ├── _exceptions_handlers.py
    ├── _groups_api.py
    ├── _groups_db.py
    ├── _groups_handlers.py
    ├── _models.py
    ├── plugin.py
    ├── _trash_api.py
    ├── _trash_handlers.py
    ├── _workspaces_api.py
    ├── _workspaces_db.py
    └── _workspaces_handlers.py





The top folders represent plugins that could be interprested as different domains with small compling between each other

Here are some conventions

- `plugin` has a setup function to setup the app (e.g. add routes, setup events etc ). Classic `setup_xxx(app)`  for aiohttp
- `settings` includes pydantic settings classes specific to the domain
- `exceptions` or `errors` include only exceptions classes
    - `_exceptions_handlers` are utils to handle exceptions
- `models` correspond to domain models, i.e. not part of any of the controllers interfaces. Those are denoted `scheme`.

Then

- `_handlers` (or _rest) represent the rest handlers (i.e. controller layer)
- `_rpc` contains handlers (server side) to an RPC interface (i.e. controller layer)
- `_api` (or `_service`) represent the business logic of this domain (i.e. service layer)
   -  the shared service layer for inter-domain logic is called `api` (i.e. without `_`)
- `_db` (or `_repository`) represents the repository layer


Could you please apply the rules on this structure and come up with a new tree that follows:
- keeps the domain-drive modular organization
- every domain implements controller-service-repository (CSR)
- highligh the shared service layer for inter-domain logic


As an output just recreate the tree adding some comments on it (e.g. with #) but no further explanatio is needed



```plaintext
├── activity
│   ├── controllers
│   │   ├── rest_handlers.py  # Rest API handlers (controller layer)
│   │   ├── rpc_handlers.py  # RPC handlers (controller layer)
│   ├── services
│   │   ├── domain_service.py  # Business logic for activity domain (service layer)
│   ├── repositories
│   │   ├── activity_repository.py  # Data access logic (repository layer)
│   ├── plugin.py  # Setup function for activity domain
│   ├── settings.py  # Domain-specific settings
│   ├── exceptions.py  # Domain-specific exceptions
├── announcements
│   ├── controllers
│   │   ├── rest_handlers.py  # Rest API handlers (controller layer)
│   │   ├── rpc_handlers.py  # RPC handlers (controller layer)
│   ├── services
│   │   ├── domain_service.py  # Business logic for announcements domain (service layer)
│   ├── repositories
│   │   ├── announcements_repository.py  # Data access logic (repository layer)
│   ├── plugin.py  # Setup function for announcements domain
│   ├── settings.py  # Domain-specific settings
│   ├── exceptions.py  # Domain-specific exceptions
├── api_keys
│   ├── controllers
│   │   ├── rest_handlers.py  # Rest API handlers (controller layer)
│   │   ├── rpc_handlers.py  # RPC handlers (controller layer)
│   ├── services
│   │   ├── domain_service.py  # Business logic for api_keys domain (service layer)
│   ├── repositories
│   │   ├── api_keys_repository.py  # Data access logic (repository layer)
│   ├── plugin.py  # Setup function for api_keys domain
│   ├── settings.py  # Domain-specific settings
│   ├── exceptions.py  # Domain-specific exceptions
├── shared_services
│   ├── inter_domain_service.py  # Shared service layer for inter-domain logic
├── db
│   ├── connection.py  # Database connection logic
│   ├── base_repository.py  # Base repository logic
│   ├── plugin.py  # Setup function for database
│   ├── settings.py  # Database-specific settings
├── catalog
│   ├── controllers
│   │   ├── rest_handlers.py  # Rest API handlers (controller layer)
│   │   ├── rpc_handlers.py  # RPC handlers (controller layer)
│   ├── services
│   │   ├── domain_service.py  # Business logic for catalog domain (service layer)
│   ├── repositories
│   │   ├── catalog_repository.py  # Data access logic (repository layer)
│   ├── plugin.py  # Setup function for catalog domain
│   ├── settings.py  # Domain-specific settings
│   ├── exceptions.py  # Domain-specific exceptions
├── users
│   ├── controllers
│   │   ├── rest_handlers.py  # Rest API handlers (controller layer)
│   │   ├── rpc_handlers.py  # RPC handlers (controller layer)
│   ├── services
│   │   ├── domain_service.py  # Business logic for users domain (service layer)
│   ├── repositories
│   │   ├── users_repository.py  # Data access logic (repository layer)
│   ├── plugin.py  # Setup function for users domain
│   ├── settings.py  # Domain-specific settings
│   ├── exceptions.py  # Domain-specific exceptions
├── projects
│   ├── controllers
│   │   ├── rest_handlers.py  # Rest API handlers (controller layer)
│   │   ├── rpc_handlers.py  # RPC handlers (controller layer)
│   ├── services
│   │   ├── domain_service.py  # Business logic for projects domain (service layer)
│   ├── repositories
│   │   ├── projects_repository.py  # Data access logic (repository layer)
│   ├── plugin.py  # Setup function for projects domain
│   ├── settings.py  # Domain-specific settings
│   ├── exceptions.py  # Domain-specific exceptions
├── shared
│   ├── models
│   │   ├── user.py  # Shared user model
│   │   ├── project.py  # Shared project model
│   ├── schemas
│   │   ├── user_schema.py  # Shared user schemas
│   │   ├── project_schema.py  # Shared project schemas
│   ├── utils
│   │   ├── logger.py  # Shared logging logic
│   │   ├── validators.py  # Shared validation logic
├── application.py  # Main application initialization
└── cli.py  # Command-line interface logic
```

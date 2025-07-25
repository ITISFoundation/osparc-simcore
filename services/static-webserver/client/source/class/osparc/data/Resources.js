/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Class that defines all the endpoints of the API to get the application resources. It also offers some convenient methods
 * to get them. It stores all the data in {osparc.store.Store} and consumes it from there whenever it is possible. The flag
 * "useCache" must be set in the resource definition.
 *
 * *Example*
 *
 * Here is a little example of how to use the class. For making calls that will update or add resources in the server,
 * such as POST and PUT calls. You can use the "fetch" method. Let's say you want to modify a study using POST.
 *
 * <pre class='javascript'>
 *   const params = {
 *     url: { // Params for the URL
 *       studyId
 *     },
 *     data: { // Payload
 *       studyData
 *     }
 *   }
 *   osparc.data.Resources.fetch("studies", "getOne", params)
 *     .then(study => {
 *       // study contains the new updated study
 *       // This code will execute if the call succeeds
 *     })
 *     .catch(err => {
 *       // Treat the error. This will execute if the call fails.
 *     });
 * </pre>
 *
 * Keep in mind that in order for this to work, the resource has to be defined in the static property resources:
 * <pre class='javascript'>
 *   statics.resources = {
 *     studies: {
 *       useCache: true, // Decide if the resources in the response have to be cached to avoid future calls
 *       endpoints: {
 *         // Define here all possible operations on this resource
 *         post: { // Second parameter of of fetch, endpoint name. The used method (post) should be contained in this name.
 *           method: "POST", // HTTP REST operation
 *           url: statics.API + "/projects/{studyId}" // Defined in params under the 'url' property
 *         }
 *       }
 *     }
 *   }
 * </pre>
 *
 * For just getting the resources without modifying them in the server, we use the dedicated methods 'get' and 'getOne'.
 * They will try to get them from the cache if they exist there. If not, they will issue the call to get them from the server.
 */

qx.Class.define("osparc.data.Resources", {
  extend: qx.core.Object,
  type: "singleton",

  defer: function(statics) {
    /*
     * Define here all resources and their endpoints.
     */
    statics.resources = {
      /*
       * CONFIG
       */
      "config": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/config"
          }
        }
      },

      /*
       * STATICS
       * Gets the json file containing some runtime server variables.
       */
      "statics": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: "/static-frontend-data.json",
            isJsonFile: true
          }
        }
      },

      /*
       * APP SUMMARY
       *  Gets the json file built by the qx compiler with some extra env variables
       * added by oSPARC as compilation vars
       */
      "appSummary": {
        useCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: "/{productName}/app-summary.json",
            isJsonFile: true
          }
        }
      },

      /*
       * STUDIES
       */
      "studies": {
        useCache: true,
        idField: "uuid",
        deleteId: "studyId",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/projects?type=user"
          },
          getOne: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}"
          },
          getServices: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/-/services"
          },
          getActive: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/active?client_session_id={tabId}"
          },
          getPage: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects?type=user&offset={offset}&limit={limit}&workspace_id={workspaceId}&folder_id={folderId}&order_by={orderBy}"
          },
          getPageSearch: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects:search?offset={offset}&limit={limit}&text={text}&order_by={orderBy}&type=user"
          },
          getPageTrashed: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects:search?filters={%22trashed%22:%22true%22}&offset={offset}&limit={limit}&order_by={orderBy}&type=user"
          },
          getWallet: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/wallet"
          },
          selectWallet: {
            method: "PUT",
            url: statics.API + "/projects/{studyId}/wallet/{walletId}"
          },
          payDebt: {
            method: "POST",
            url: statics.API + "/projects/{studyId}/wallet/{walletId}:pay-debt"
          },
          duplicate: {
            method: "POST",
            // url: statics.API + "/projects/{studyId}:duplicate"
            // supports copy_data
            url: statics.API + "/projects?from_study={studyId}"
          },
          state: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/state"
          },
          postNewStudy: {
            method: "POST",
            url: statics.API + "/projects"
          },
          postNewStudyFromTemplate: {
            method: "POST",
            url: statics.API + "/projects?from_study={templateId}"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/projects/{studyId}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/projects/{studyId}"
          },
          addNode: {
            useCache: false,
            method: "POST",
            url: statics.API + "/projects/{studyId}/nodes"
          },
          startNode: {
            useCache: false,
            method: "POST",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}:start"
          },
          stopNode: {
            useCache: false,
            method: "POST",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}:stop"
          },
          getNode: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}"
          },
          patchNode: {
            method: "PATCH",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}"
          },
          deleteNode: {
            useCache: false,
            method: "DELETE",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}"
          },
          getNodeErrors: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}/errors"
          },
          getPricingUnit: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}/pricing-unit"
          },
          putPricingUnit: {
            method: "PUT",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}/pricing-plan/{pricingPlanId}/pricing-unit/{pricingUnitId}"
          },
          postAccessRights: {
            useCache: false,
            method: "POST",
            url: statics.API + "/projects/{studyId}/groups/{gId}"
          },
          deleteAccessRights: {
            useCache: false,
            method: "DELETE",
            url: statics.API + "/projects/{studyId}/groups/{gId}"
          },
          putAccessRights: {
            useCache: false,
            method: "PUT",
            url: statics.API + "/projects/{studyId}/groups/{gId}"
          },
          addTag: {
            useCache: false,
            method: "POST",
            url: statics.API + "/projects/{studyId}/tags/{tagId}:add"
          },
          removeTag: {
            useCache: false,
            method: "POST",
            url: statics.API + "/projects/{studyId}/tags/{tagId}:remove"
          },
          getInactivity: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/inactivity"
          },
          moveToFolder: {
            method: "PUT",
            url: statics.API + "/projects/{studyId}/folders/{folderId}"
          },
          moveToWorkspace: {
            method: "POST",
            url: statics.API + "/projects/{studyId}/workspaces/{workspaceId}:move"
          },
          updateMetadata: {
            method: "PATCH",
            url: statics.API + "/projects/{studyId}/metadata"
          },
          open: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:open"
          },
          openDisableAutoStart: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:open?disable_service_auto_start={disableServiceAutoStart}"
          },
          close: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:close"
          },
          shareWithEmail: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:share"
          },
          checkShareePermissions: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/-/services:access?for_gid={gid}"
          },
          trash: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:trash"
          },
          untrash: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:untrash"
          },
        }
      },
      "conversations": {
        useCache: false, // It has its own cache handler
        endpoints: {
          addConversation: {
            method: "POST",
            url: statics.API + "/projects/{studyId}/conversations"
          },
          getConversationsPage: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/conversations?offset={offset}&limit={limit}"
          },
          getConversation: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/conversations/{conversationId}"
          },
          renameConversation: {
            method: "PUT",
            url: statics.API + "/projects/{studyId}/conversations/{conversationId}"
          },
          deleteConversation: {
            method: "DELETE",
            url: statics.API + "/projects/{studyId}/conversations/{conversationId}"
          },
          addMessage: {
            method: "POST",
            url: statics.API + "/projects/{studyId}/conversations/{conversationId}/messages"
          },
          editMessage: {
            method: "PUT",
            url: statics.API + "/projects/{studyId}/conversations/{conversationId}/messages/{messageId}"
          },
          deleteMessage: {
            method: "DELETE",
            url: statics.API + "/projects/{studyId}/conversations/{conversationId}/messages/{messageId}"
          },
          getMessagesPage: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/conversations/{conversationId}/messages?offset={offset}&limit={limit}"
          },
        }
      },
      "runPipeline": {
        useCache: false,
        endpoints: {
          startPipeline: {
            method: "POST",
            url: statics.API + "/computations/{studyId}:start"
          },
          stopPipeline: {
            method: "POST",
            url: statics.API + "/computations/{studyId}:stop"
          },
        }
      },
      "runs": {
        useCache: false, // handled in osparc.store.Jobs
        endpoints: {
          getPageLatest: {
            method: "GET",
            url: statics.API + "/computation-collection-runs?offset={offset}&limit={limit}&order_by={orderBy}&filter_only_running={runningOnly}"
          },
          getPageHistory: {
            method: "GET",
            url: statics.API + "/computation-collection-runs?offset={offset}&limit={limit}&order_by={orderBy}&filter_by_root_project_id={projectId}"
          },
        }
      },
      "subRuns": {
        useCache: false, // handled in osparc.store.Jobs
        endpoints: {
          getPageLatest: {
            method: "GET",
            url: statics.API + "/computation-collection-runs/{collectionRunId}/tasks?offset={offset}&limit={limit}&order_by={orderBy}"
          },
        }
      },
      "folders": {
        useCache: true,
        idField: "uuid",
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/folders?workspace_id={workspaceId}&folder_id={folderId}&offset={offset}&limit={limit}&order_by={orderBy}"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/folders/{folderId}"
          },
          getPageSearch: {
            useCache: false,
            method: "GET",
            url: statics.API + "/folders:search?offset={offset}&limit={limit}&text={text}&order_by={orderBy}"
          },
          getPageTrashed: {
            useCache: false,
            method: "GET",
            url: statics.API + "/folders:search?filters={%22trashed%22:%22true%22}&offset={offset}&limit={limit}&order_by={orderBy}"
          },
          post: {
            method: "POST",
            url: statics.API + "/folders"
          },
          update: {
            method: "PUT",
            url: statics.API + "/folders/{folderId}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/folders/{folderId}"
          },
          moveToWorkspace: {
            method: "POST",
            url: statics.API + "/folders/{folderId}/workspaces/{workspaceId}:move"
          },
          trash: {
            method: "POST",
            url: statics.API + "/folders/{folderId}:trash"
          },
          untrash: {
            method: "POST",
            url: statics.API + "/folders/{folderId}:untrash"
          },
        }
      },
      "workspaces": {
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/workspaces?&offset={offset}&limit={limit}"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/workspaces/{workspaceId}"
          },
          getPageSearch: {
            useCache: false,
            method: "GET",
            url: statics.API + "/workspaces?offset={offset}&limit={limit}&filters={filters}&order_by={orderBy}"
          },
          getPageTrashed: {
            useCache: false,
            method: "GET",
            // url: statics.API + "/workspaces:search?filters={%22trashed%22:%22true%22}&offset={offset}&limit={limit}&order_by={orderBy}"
            url: statics.API + "/workspaces?filters={%22trashed%22:%22true%22}&offset={offset}&limit={limit}&order_by={orderBy}"
          },
          post: {
            method: "POST",
            url: statics.API + "/workspaces"
          },
          update: {
            method: "PUT",
            url: statics.API + "/workspaces/{workspaceId}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/workspaces/{workspaceId}"
          },
          trash: {
            method: "POST",
            url: statics.API + "/workspaces/{workspaceId}:trash"
          },
          untrash: {
            method: "POST",
            url: statics.API + "/workspaces/{workspaceId}:untrash"
          },
          postAccessRights: {
            method: "POST",
            url: statics.API + "/workspaces/{workspaceId}/groups/{groupId}"
          },
          putAccessRights: {
            method: "PUT",
            url: statics.API + "/workspaces/{workspaceId}/groups/{groupId}"
          },
          deleteAccessRights: {
            method: "DELETE",
            url: statics.API + "/workspaces/{workspaceId}/groups/{groupId}"
          },
        }
      },
      "resourceUsage": {
        useCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/services/-/resource-usages?offset={offset}&limit={limit}&filters={filters}&order_by={orderBy}"
          },
          getWithWallet: {
            method: "GET",
            url: statics.API + "/services/-/resource-usages?wallet_id={walletId}&offset={offset}&limit={limit}"
          },
          getWithWalletFiltered: {
            method: "GET",
            url: statics.API + "/services/-/resource-usages?wallet_id={walletId}&offset={offset}&limit={limit}&filters={filters}&order_by={orderBy}"
          },
          getUsagePerService: {
            method: "GET",
            url: statics.API + "/services/-/aggregated-usages?wallet_id={walletId}&aggregated_by=services&time_period={timePeriod}"
          }
        }
      },
      /*
       * NODES
       */
      "nodesInStudyResources": {
        idField: ["studyId", "nodeId"],
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}/resources"
          },
          put: {
            method: "PUT",
            url: statics.API + "/projects/{studyId}/nodes/{nodeId}/resources"
          }
        }
      },

      /*
       * TRASH
       */
      "trash": {
        endpoints: {
          delete: {
            method: "POST",
            url: statics.API + "/trash:empty"
          }
        }
      },

      /*
       * SNAPSHOTS
       */
      "snapshots": {
        idField: "uuid",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/repos/projects/{studyId}/checkpoints"
          },
          getPage: {
            method: "GET",
            url: statics.API + "/repos/projects/{studyId}/checkpoints?offset={offset}&limit={limit}"
          },
          getOne: {
            useCache: false,
            method: "GET",
            url: statics.API + "/repos/projects/{studyId}/checkpoints/{snapshotId}"
          },
          updateSnapshot: {
            method: "PATCH",
            url: statics.API + "/repos/projects/{studyId}/checkpoints/{snapshotId}"
          },
          currentCommit: {
            method: "GET",
            url: statics.API + "/repos/projects/{studyId}/checkpoints/HEAD"
          },
          checkout: {
            method: "POST",
            url: statics.API + "/repos/projects/{studyId}/checkpoints/{snapshotId}:checkout"
          },
          preview: {
            useCache: false,
            method: "GET",
            url: statics.API + "/repos/projects/{studyId}/checkpoints/{snapshotId}/workbench/view"
          },
          getParameters: {
            useCache: false,
            method: "GET",
            url: statics.API + "/repos/projects/{studyId}/checkpoints/{snapshotId}/parameters"
          },
          takeSnapshot: {
            method: "POST",
            url: statics.API + "/repos/projects/{studyId}/checkpoints"
          }
        }
      },
      /*
       * ITERATIONS
       */
      "iterations": {
        idField: "uuid",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/checkpoint/{snapshotId}/iterations"
          },
          createIterations: {
            method: "POST",
            url: statics.API + "/projects/{studyId}/checkpoint/{snapshotId}/iterations"
          }
        }
      },
      /*
       * TEMPLATES (actually studies flagged as templates)
       */
      "templates": {
        useCache: true,
        idField: "uuid",
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/projects?type=template&offset={offset}&limit={limit}"
          },
          getPageFilteredSorted: {
            method: "GET",
            url: statics.API + "/projects?type=template&offset={offset}&limit={limit}&order_by={orderBy}&template_type={templateType}"
          },
          getPageSearchFilteredSorted: {
            method: "GET",
            url: statics.API + "/projects:search?type=template&offset={offset}&limit={limit}&order_by={orderBy}&template_type={templateType}&text={text}"
          },
          postToTemplate: {
            method: "POST",
            url: statics.API + "/projects?from_study={study_id}&as_template=true&copy_data={copy_data}&hidden={hidden}"
          },
        }
      },
      /*
       * FUNCTIONS
       */
      "functions": {
        useCache: false,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/functions/{functionId}?include_extras=true"
          },
          getPage: {
            method: "GET",
            url: statics.API + "/functions?include_extras=true&offset={offset}&limit={limit}"
          },
          create: {
            method: "POST",
            url: statics.API + "/functions"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/functions/{functionId}?include_extras=true"
          },
        }
      },
      /*
       * TASKS
       */
      "tasks": {
        useCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/tasks"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/tasks/{taskId}"
          }
        }
      },

      /*
       * SERVICES
       */
      "services": {
        useCache: false, // handled in osparc.store.Services
        idField: ["key", "version"],
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/catalog/services/{key}/{version}"
          },
          getPage: {
            method: "GET",
            url: statics.API + "/catalog/services/-/latest?offset={offset}&limit={limit}"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/catalog/services/{key}/{version}"
          },
          pricingPlans: {
            useCache: false,
            method: "GET",
            url: statics.API + "/catalog/services/{key}/{version}/pricing-plan"
          },
        }
      },

      /*
       * PORTS COMPATIBILITY
       */
      "portsCompatibility": {
        useCache: false, // It has its own cache handler
        endpoints: {
          matchInputs: {
            // get_compatible_inputs_given_source_output_handler
            method: "GET",
            url: statics.API + "/catalog/services/{serviceKey2}/{serviceVersion2}/inputs:match?fromService={serviceKey1}&fromVersion={serviceVersion1}&fromOutput={portKey1}"
          },
          matchOutputs: {
            useCache: false,
            // get_compatible_outputs_given_target_input_handler
            method: "GET",
            url: statics.API + "/catalog/services/{serviceKey1}/{serviceVersion1}/outputs:match?fromService={serviceKey2}&fromVersion={serviceVersion2}&fromOutput={portKey2}"
          }
        }
      },

      /*
       * SERVICE RESOURCES
       */
      "serviceResources": {
        idField: ["key", "version"],
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/catalog/services/{key}/{version}/resources"
          }
        }
      },

      /*
       * ADMIN PRICING PLANS
       */
      "adminPricingPlans": {
        useCache: false, // handled in osparc.store.Pricing
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/admin/pricing-plans?offset={offset}&limit={limit}"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/admin/pricing-plans/{pricingPlanId}"
          },
          update: {
            method: "PUT",
            url: statics.API + "/admin/pricing-plans/{pricingPlanId}"
          },
          post: {
            method: "POST",
            url: statics.API + "/admin/pricing-plans"
          },
        }
      },

      /*
       * PRICING PLANS
       */
      "pricingPlans": {
        useCache: false, // handled in osparc.store.Pricing
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/pricing-plans?offset={offset}&limit={limit}"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/pricing-plans/{pricingPlanId}"
          },
        }
      },

      /*
       * PRICING UNITS
       */
      "pricingUnits": {
        useCache: false, // handled in osparc.store.Pricing
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/admin/pricing-plans/{pricingPlanId}/pricing-units/{pricingUnitId}"
          },
          update: {
            method: "PUT",
            url: statics.API + "/admin/pricing-plans/{pricingPlanId}/pricing-units/{pricingUnitId}"
          },
          post: {
            method: "POST",
            url: statics.API + "/admin/pricing-plans/{pricingPlanId}/pricing-units"
          },
        }
      },

      /*
       * BILLABLE SERVICES
       */
      "billableServices": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/admin/pricing-plans/{pricingPlanId}/billable-services"
          },
          post: {
            method: "POST",
            url: statics.API + "/admin/pricing-plans/{pricingPlanId}/billable-services"
          },
        }
      },

      /*
       * SCHEDULED MAINTENANCE
       * Example: {"start": "2023-01-17T14:45:00.000Z", "end": "2023-01-17T23:00:00.000Z", "reason": "Release 1.0.4"}
       */
      "maintenance": {
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/scheduled_maintenance"
          }
        }
      },
      /*
       * ANNOUNCEMENTS
       */
      "announcements": {
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/announcements"
          }
        }
      },
      /*
       * PROFILE
       */
      "profile": {
        useCache: true,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/me"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/me"
          },
        }
      },
      /*
       * PREFERENCES
       */
      "preferences": {
        endpoints: {
          patch: {
            method: "PATCH",
            url: statics.API + "/me/preferences/{preferenceId}"
          }
        }
      },
      /*
       * PERMISSIONS
       */
      "permissions": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/me/permissions"
          }
        }
      },
      /*
       * FUNCTION PERMISSIONS
       */
      "functionPermissions": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/me/function-permissions"
          }
        }
      },
      /*
       * API-KEYS
       */
      "apiKeys": {
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/auth/api-keys"
          },
          post: {
            method: "POST",
            url: statics.API + "/auth/api-keys"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/auth/api-keys/{apiKeyId}"
          }
        }
      },
      /*
       * TOKENS
       */
      "tokens": {
        useCache: true,
        idField: "service",
        deleteId: "service",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/me/tokens"
          },
          post: {
            method: "POST",
            url: statics.API + "/me/tokens"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/me/tokens/{service}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/me/tokens/{service}"
          },
          put: {
            method: "PUT",
            url: statics.API + "/me/tokens/{service}"
          }
        }
      },
      /*
       * NOTIFICATIONS
       */
      "notifications": {
        useCache: false,
        idField: "notification",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/me/notifications"
          },
          post: {
            method: "POST",
            url: statics.API + "/me/notifications"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/me/notifications/{notificationId}"
          }
        }
      },
      /*
       * ORGANIZATIONS
       */
      "organizations": {
        useCache: false, // osparc.store.Groups handles the cache
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/groups"
          },
          post: {
            method: "POST",
            url: statics.API + "/groups"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/groups/{gid}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/groups/{gid}"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/groups/{gid}"
          }
        }
      },
      /*
       * ORGANIZATION MEMBERS
       */
      "organizationMembers": {
        useCache: false, // osparc.store.Groups handles the cache
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/groups/{gid}/users"
          },
          post: {
            method: "POST",
            url: statics.API + "/groups/{gid}/users"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/groups/{gid}/users/{uid}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/groups/{gid}/users/{uid}"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/groups/{gid}/users/{uid}"
          }
        }
      },
      /*
       * USERS
       */
      "users": {
        useCache: false, // osparc.store.Groups handles the cache
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/groups/{gid}/users"
          },
          search: {
            method: "POST",
            url: statics.API + "/users:search"
          }
        }
      },
      /*
       * WALLETS
       */
      "wallets": {
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/wallets"
          },
          post: {
            method: "POST",
            url: statics.API + "/wallets"
          },
          put: {
            method: "PUT",
            url: statics.API + "/wallets/{walletId}"
          },
          getAccessRights: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/groups"
          },
          putAccessRights: {
            method: "PUT",
            url: statics.API + "/wallets/{walletId}/groups/{groupId}"
          },
          postAccessRights: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/groups/{groupId}"
          },
          deleteAccessRights: {
            method: "DELETE",
            url: statics.API + "/wallets/{walletId}/groups/{groupId}"
          },
          getAutoRecharge: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/auto-recharge"
          },
          putAutoRecharge: {
            method: "PUT",
            url: statics.API + "/wallets/{walletId}/auto-recharge"
          },
        }
      },
      /*
       * PRODUCTS
       */
      "creditPrice": {
        useCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/credits-price"
          }
        }
      },
      "productMetadata": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/products/{productName}"
          },
          updateEmailTemplate: {
            method: "PUT",
            url: statics.API + "/products/{productName}/templates/{templateId}"
          },
          getUiConfig: {
            method: "GET",
            url: statics.API + "/products/current/ui"
          },
        }
      },
      "invitations": {
        endpoints: {
          post: {
            method: "POST",
            url: statics.API + "/invitation:generate"
          }
        }
      },
      "poUsers": {
        endpoints: {
          search: {
            method: "GET",
            url: statics.API + "/admin/user-accounts:search?email={email}"
          },
          getPendingUsers: {
            method: "GET",
            url: statics.API + "/admin/user-accounts?review_status=PENDING"
          },
          getReviewedUsers: {
            method: "GET",
            url: statics.API + "/admin/user-accounts?review_status=REVIEWED"
          },
          approveUser: {
            method: "POST",
            url: statics.API + "/admin/user-accounts:approve"
          },
          rejectUser: {
            method: "POST",
            url: statics.API + "/admin/user-accounts:reject"
          },
          resendConfirmationEmail: {
            method: "POST",
            url: statics.API + "/admin/user-accounts:resendConfirmationEmail"
          },
          preRegister: {
            method: "POST",
            url: statics.API + "/admin/user-accounts:pre-register"
          }
        }
      },
      /*
       * PAYMENTS
       */
      "payments": {
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/wallets/-/payments?offset={offset}&limit={limit}"
          },
          startPayment: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/payments"
          },
          cancelPayment: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/payments/{paymentId}:cancel"
          },
          payWithPaymentMethod: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/payments-methods/{paymentMethodId}:pay"
          },
          invoiceLink: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/payments/{paymentId}/invoice-link"
          }
        }
      },
      /*
       * PAYMENT METHODS
       */
      "paymentMethods": {
        useCache: false,
        endpoints: {
          init: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/payments-methods:init"
          },
          cancel: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/payments-methods/{paymentMethodId}:cancel"
          },
          get: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/payments-methods"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/wallets/{walletId}/payments-methods/{paymentMethodId}"
          }
        }
      },
      /*
       * AUTO RECHARGE
       */
      "autoRecharge": {
        useCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/auto-recharge"
          },
          put: {
            method: "PUT",
            url: statics.API + "/wallets/{walletId}/auto-recharge"
          }
        }
      },
      /*
       * CLASSIFIERS
       * Gets the json object containing sample classifiers
       */
      "classifiers": {
        useCache: false,
        idField: "classifiers",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/groups/{gid}/classifiers"
          },
          postRRID: {
            method: "POST",
            url: statics.API + "/groups/sparc/classifiers/scicrunch-resources/{rrid}"
          }
        }
      },

      /*
       * PASSWORD
       */
      "password": {
        useCache: false,
        endpoints: {
          post: {
            method: "POST",
            url: statics.API + "/auth/change-password"
          }
        }
      },
      /*
       * AUTH
       */
      "auth": {
        useCache: false,
        endpoints: {
          postRegister: {
            method: "POST",
            url: statics.API + "/auth/register"
          },
          postRequestAccount: {
            method: "POST",
            url: statics.API + "/auth/request-account"
          },
          captcha: {
            method: "POST",
            url: statics.API + "/auth/captcha"
          },
          checkInvitation: {
            method: "POST",
            url: statics.API + "/auth/register/invitations:check"
          },
          unregister: {
            method: "POST",
            url: statics.API + "/auth/unregister"
          },
          verifyPhoneNumber: {
            method: "POST",
            url: statics.API + "/auth/verify-phone-number"
          },
          validateCodeRegister: {
            method: "POST",
            url: statics.API + "/auth/validate-code-register"
          },
          resendCode: {
            method: "POST",
            url: statics.API + "/auth/two_factor:resend"
          },
          postLogin: {
            method: "POST",
            url: statics.API + "/auth/login"
          },
          validateCodeLogin: {
            method: "POST",
            url: statics.API + "/auth/validate-code-login"
          },
          postLogout: {
            method: "POST",
            url: statics.API + "/auth/logout"
          },
          postRequestResetPassword: {
            method: "POST",
            url: statics.API + "/auth/reset-password"
          },
          postResetPassword: {
            method: "POST",
            url: statics.API + "/auth/reset-password/{code}"
          },
          changeEmail: {
            method: "POST",
            url: statics.API + "/auth/change-email"
          },
        }
      },
      /*
       * STORAGE LOCATIONS
       */
      "storageLocations": {
        useCache: true,
        endpoints: {
          getLocations: {
            method: "GET",
            url: statics.API + "/storage/locations"
          }
        }
      },
      /*
       * STORAGE FILES
       */
      "storageFiles": {
        useCache: false,
        endpoints: {
          copy: {
            method: "PUT",
            url: statics.API + "/storage/locations/{toLoc}/files/{fileName}?extra_location={fromLoc}&extra_source={fileUuid}"
          }
        }
      },
      /*
       * STORAGE PATHS
       */
      "storagePaths": {
        useCache: false,
        endpoints: {
          getDatasets: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/paths?size=1000"
          },
          getDatasetsPage: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/paths?cursor={cursor}&size=1000"
          },
          getPaths: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/paths?file_filter={path}&size=1000"
          },
          getPathsPage: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/paths?file_filter={path}&cursor={cursor}&size=1000"
          },
          multiDownload: {
            method: "POST",
            url: statics.API + "/storage/locations/{locationId}/export-data"
          },
          batchDelete: {
            method: "POST",
            url: statics.API + "/storage/locations/{locationId}/-/paths:batchDelete"
          },
          requestSize: {
            method: "POST",
            url: statics.API + "/storage/locations/0/paths/{pathId}:size"
          },
        }
      },
      /*
       * STORAGE LINK
       */
      "storageLink": {
        useCache: false,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/files/{fileUuid}"
          },
          put: {
            method: "PUT",
            url: statics.API + "/storage/locations/{locationId}/files/{fileUuid}?file_size={fileSize}"
          }
        }
      },
      /*
       * ACTIVITY
       */
      "activity": {
        useCache: false,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/activity/status"
          }
        }
      },

      /*
       * Test/Diagnostic entrypoint
       */
      "checkEP": {
        useCache: false,
        endpoints: {
          postFail: {
            method: "POST",
            url: statics.API + "/check/fail"
          },
          postEcho: {
            method: "POST",
            url: statics.API + "/check/echo"
          }
        }
      },

      /*
       * TAGS
       */
      "tags": {
        useCache: true,
        idField: "id",
        deleteId: "tagId",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/tags"
          },
          post: {
            method: "POST",
            url: statics.API + "/tags"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/tags/{tagId}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/tags/{tagId}"
          },
          getAccessRights: {
            method: "GET",
            url: statics.API + "/tags/{tagId}/groups"
          },
          putAccessRights: {
            method: "PUT",
            url: statics.API + "/tags/{tagId}/groups/{groupId}"
          },
          postAccessRights: {
            method: "POST",
            url: statics.API + "/tags/{tagId}/groups/{groupId}"
          },
          deleteAccessRights: {
            method: "DELETE",
            url: statics.API + "/tags/{tagId}/groups/{groupId}"
          },
        }
      },

      /*
       * LICENSED ITEMS
       */
      "licensedItems": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/catalog/licensed-items"
          },
          getPage: {
            method: "GET",
            url: statics.API + "/catalog/licensed-items?offset={offset}&limit={limit}"
          },
          purchases: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/licensed-items-purchases?offset={offset}&limit={limit}"
          },
          purchase: {
            method: "POST",
            url: statics.API + "/catalog/licensed-items/{licensedItemId}:purchase"
          },
          checkouts: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/licensed-items-checkouts?offset={offset}&limit={limit}"
          },
        }
      }
    };
  },

  members: {
    __portsCompatibilityPromisesCached: null,

    /**
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {String} endpoint Name of the endpoint. Several endpoints can be defined for each resource.
     * @param {Object} urlParams Object containing only the parameters for the url of the request.
     */
    replaceUrlParams: function(resource, endpoint, urlParams) {
      const resourceDefinition = this.self().resources[resource];
      const res = new osparc.io.rest.Resource(resourceDefinition.endpoints);
      // Use qooxdoo's Get request configuration
      // eslint-disable-next-line no-underscore-dangle
      const getReqConfig = res._resource._getRequestConfig(endpoint, urlParams);
      return getReqConfig;
    },

    /**
     * Method to fetch resources from the server. If configured properly, the resources in the response will be cached in {osparc.store.Store}.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {String} endpoint Name of the endpoint. Several endpoints can be defined for each resource.
     * @param {Object} params Object containing the parameters for the url and for the body of the request, under the properties 'url' and 'data', respectively.
     * @param {Object} options Collections of options (pollTask, resolveWResponse, timeout, timeoutRetries)
     */
    fetch: function(resource, endpoint, params = {}, options = {}) {
      if (params === null) {
        params = {};
      }
      if (options === null) {
        options = {};
      }
      return new Promise((resolve, reject) => {
        if (this.self().resources[resource] == null) {
          reject(Error(`Error while fetching ${resource}: the resource is not defined`));
        }

        const resourceDefinition = this.self().resources[resource];
        const res = new osparc.io.rest.Resource(resourceDefinition.endpoints, options.timeout);
        if (!res.includesRoute(endpoint)) {
          reject(Error(`Error while fetching ${resource}: the endpoint is not defined`));
        }

        const sendRequest = () => {
          res[endpoint](params.url || null, params.data || null);
        }

        const successCB = e => {
          const response = e.getRequest().getResponse();
          const endpointDef = resourceDefinition.endpoints[endpoint];
          const data = endpointDef.isJsonFile ? response : response.data;
          // OM: Temporary solution until the quality object is better defined
          if (data && endpoint.includes("get") && ["studies", "templates"].includes(resource)) {
            if (Array.isArray(data)) {
              data.forEach(std => {
                osparc.metadata.Quality.attachQualityToObject(std);
              });
            } else {
              osparc.metadata.Quality.attachQualityToObject(data);
            }
          }

          const useCache = ("useCache" in endpointDef) ? endpointDef.useCache : resourceDefinition.useCache;
          if (useCache) {
            if (endpoint.includes("delete") && resourceDefinition["deleteId"] && resourceDefinition["deleteId"] in params.url) {
              const deleteId = params.url[resourceDefinition["deleteId"]];
              this.__removeCached(resource, deleteId);
            } else if (endpointDef.method === "POST" && options.pollTask !== true) {
              this.__addCached(resource, data);
            } else if (endpointDef.method === "GET") {
              if (endpoint.includes("getPage")) {
                this.__addCached(resource, data);
              } else {
                this.__setCached(resource, data);
              }
            }
          }

          res.dispose();

          if ("resolveWResponse" in options && options.resolveWResponse) {
            response.params = params;
            resolve(response);
          } else {
            resolve(data);
          }
        };

        const errorCB = e => {
          if (e.getPhase() === "timeout") {
            if (options.timeout && options.timeoutRetries) {
              options.timeoutRetries--;
              sendRequest();
              return;
            }
          }

          let message = null;
          let status = null;
          let supportId = null;
          if (e.getData().error) {
            const errorData = e.getData().error;
            if (errorData.message) {
              message = errorData.message;
            }
            const logs = errorData.logs || null;
            if (message === null && logs && logs.length) {
              message = logs[0].message;
            }
            const errors = errorData.errors || [];
            if (message === null && errors && errors.length) {
              message = errors[0].message;
            }
            status = errorData.status;
            if (errorData["support_id"]) {
              supportId = errorData["support_id"];
            }
          } else {
            const req = e.getRequest();
            message = req.getResponse();
            status = req.getStatus();
          }
          res.dispose();

          // If a 401 is received, make a call to the /me endpoint.
          // If the backend responds with yet another 401, assume that the backend logged the user out
          if (status === 401 && resource !== "profile" && osparc.auth.Manager.getInstance().isLoggedIn()) {
            console.warn("Checking if user is logged in the backend");
            this.fetch("profile", "getOne")
              .catch(err => {
                if ("status" in err && err.status === 401) {
                  // Unauthorized again, the cookie might have expired.
                  // We can assume that all calls after this will respond with 401, so bring the user ot the login page.
                  qx.core.Init.getApplication().logout(qx.locale.Manager.tr("You have been logged out. Your cookie might have expired."));
                }
              });
          }

          if ([404, 503].includes(status)) {
            // NOTE: a temporary solution to avoid duplicate information
            if (!message.includes("contact") && !message.includes("try")) {
              message += "<br>Please try again later and/or contact support";
            }
          }
          const err = Error(message ? message : `Error while trying to fetch ${endpoint} ${resource}`);
          if (status) {
            err.status = status;
          }
          if (supportId) {
            err.supportId = supportId;
          }
          reject(err);
        };

        const successEndpoint = endpoint + "Success";
        const errorEndpoint = endpoint + "Error";
        res.addListenerOnce(successEndpoint, e => successCB(e), this);
        res.addListener(errorEndpoint, e => errorCB(e), this);
        sendRequest();
      });
    },

    getAllPages: function(resource, params = {}, endpoint = "getPage") {
      return new Promise((resolve, reject) => {
        let resources = [];
        let offset = 0;
        if (!("url" in params)) {
          params["url"] = {};
        }
        params["url"]["offset"] = offset;
        params["url"]["limit"] = 10;
        const options = {
          resolveWResponse: true
        };
        this.fetch(resource, endpoint, params, options)
          .then(resp => {
            // sometimes there is a kind of a double "data"
            const meta = ("_meta" in resp["data"]) ? resp["data"]["_meta"] : resp["_meta"];
            const data = ("_meta" in resp["data"]) ? resp["data"]["data"] : resp["data"];
            resources = [...resources, ...data];
            const allRequests = [];
            for (let i=offset+meta.limit; i<meta.total; i+=meta.limit) {
              params.url.offset = i;
              allRequests.push(this.fetch(resource, endpoint, params));
            }
            Promise.all(allRequests)
              .then(resps => {
                // sometimes there is a kind of a double "data"
                resps.forEach(respData => {
                  if ("data" in respData) {
                    resources = [...resources, ...respData["data"]]
                  } else {
                    resources = [...resources, ...respData]
                  }
                });
                resolve(resources);
              })
              .catch(err => {
                console.error(err);
                reject(err);
              });
          })
          .catch(err => {
            console.error(err);
            reject(err);
          });
      });
    },

    /**
     * Get a single resource or a specific resource inside a collection.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {Object} params Object containing the parameters for the url and for the body of the request, under the properties 'url' and 'data', respectively.
     * @param {String} id Id(s) of the element to get, if it is a collection of elements.
     * @param {Boolean} useCache Whether the cache has to be used. If false, an API call will be issued.
     */
    getOne: function(resource, params, id, useCache = true) {
      if (useCache) {
        const stored = this.__getCached(resource);
        if (stored) {
          const idField = this.self().resources[resource].idField || "uuid";
          const idFields = Array.isArray(idField) ? idField : [idField];
          const ids = Array.isArray(id) ? id : [id];
          const item = Array.isArray(stored) ? stored.find(element => idFields.every(idF => element[idF] === ids[idF])) : stored;
          if (item) {
            return Promise.resolve(item);
          }
        }
      }
      return this.fetch(resource, "getOne", params || {});
    },

    /**
     * Get a single resource or the entire collection.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {Object} params Object containing the parameters for the url and for the body of the request, under the properties 'url' and 'data', respectively.
     * @param {Boolean} useCache Whether the cache has to be used. If false, an API call will be issued.
     */
    get: function(resource, params = {}, useCache = true, options = {}) {
      if (useCache) {
        const stored = this.__getCached(resource);
        if (stored) {
          return Promise.resolve(stored);
        }
      }
      return this.fetch(resource, "get", params, options);
    },

    /**
     * Returns the cached version of the resource or null if empty.
     * @param {String} resource Resource name
     */
    __getCached: function(resource) {
      let stored;
      try {
        stored = osparc.store.Store.getInstance().get(resource);
      } catch (err) {
        return null;
      }
      if (stored === null) {
        return null;
      }
      if (typeof stored === "object" && Object.keys(stored).length === 0) {
        return null;
      }
      if (Array.isArray(stored) && stored.length === 0) {
        return null;
      }
      return stored;
    },

    /**
     * Stores the cached version of a resource, or a collection of them.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {*} data Resource or collection of resources to be cached.
     */
    __setCached: function(resource, data) {
      osparc.store.Store.getInstance().update(resource, data, this.self().resources[resource].idField || "uuid");
    },

    /**
     * Add the given data to the cached version of a resource, or a collection of them.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {*} data Resource or collection of resources to be added to the cache.
     */
    __addCached: function(resource, data) {
      osparc.store.Store.getInstance().append(resource, data, this.self().resources[resource].idField || "uuid");
    },

    /**
     * Removes an element from the cache.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {String} deleteId Id of the item to remove from cache.
     */
    __removeCached: function(resource, deleteId) {
      osparc.store.Store.getInstance().remove(resource, this.self().resources[resource].idField || "uuid", deleteId);
    },

    getCompatibleInputs: function(node1, portId1, node2) {
      const url = {
        "serviceKey2": encodeURIComponent(node2.getKey()),
        "serviceVersion2": node2.getVersion(),
        "serviceKey1": encodeURIComponent(node1.getKey()),
        "serviceVersion1": node1.getVersion(),
        "portKey1": portId1
      };

      const cachedCPs = this.__getCached("portsCompatibility") || {};
      const strUrl = JSON.stringify(url);
      if (strUrl in cachedCPs) {
        return Promise.resolve(cachedCPs[strUrl]);
      }

      // avoid request deduplication
      if (this.__portsCompatibilityPromisesCached === null) {
        this.__portsCompatibilityPromisesCached = {};
      }
      if (strUrl in this.__portsCompatibilityPromisesCached) {
        return this.__portsCompatibilityPromisesCached[strUrl];
      }

      const params = {
        url
      };
      this.__portsCompatibilityPromisesCached[strUrl] = this.fetch("portsCompatibility", "matchInputs", params)
        .then(data => {
          cachedCPs[strUrl] = data;
          this.__setCached("portsCompatibility", cachedCPs);
          return data;
        })
        .finally(() => {
          // Remove the promise from the cache
          delete this.__portsCompatibilityPromisesCached[strUrl];
        });

      return this.__portsCompatibilityPromisesCached[strUrl];
    },
  },

  statics: {
    API: "/v0",
    fetch: function(resource, endpoint, params, options = {}) {
      return this.getInstance().fetch(resource, endpoint, params, options);
    },
    getOne: function(resource, params, id, useCache) {
      return this.getInstance().getOne(resource, params, id, useCache);
    },
    get: function(resource, params, useCache, options) {
      return this.getInstance().get(resource, params, useCache, options);
    },

    getServiceUrl: function(key, version) {
      return {
        "key": encodeURIComponent(key),
        "version": version
      };
    },

    getErrorMsg: function(resp) {
      const error = resp["error"];
      return error ? error["errors"][0].message : null;
    }
  }
});

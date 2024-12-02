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
            url: statics.API + "/projects:search?offset={offset}&limit={limit}&text={text}&tag_ids={tagIds}&order_by={orderBy}"
          },
          getPageTrashed: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects?filters={%22trashed%22:%22true%22}&offset={offset}&limit={limit}&order_by={orderBy}"
          },
          postToTemplate: {
            method: "POST",
            url: statics.API + "/projects?from_study={study_id}&as_template=true&copy_data={copy_data}"
          },
          open: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:open"
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
          openDisableAutoStart: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:open?disable_service_auto_start={disableServiceAutoStart}"
          },
          close: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:close"
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
          trash: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:trash"
          },
          untrash: {
            method: "POST",
            url: statics.API + "/projects/{studyId}:untrash"
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
          checkShareePermissions: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/-/services:access?for_gid={gid}"
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
            method: "PUT",
            url: statics.API + "/projects/{studyId}/workspaces/{workspaceId}"
          },
        }
      },
      "studyComments": {
        useCache: true,
        idField: "uuid",
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/comments?offset={offset}&limit={limit}"
          },
          addComment: {
            method: "POST",
            url: statics.API + "/projects/{studyId}/comments"
          }
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
            url: statics.API + "/folders?filters={%22trashed%22:%22true%22}&offset={offset}&limit={limit}&order_by={orderBy}"
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
            method: "PUT",
            url: statics.API + "/folders/{folderId}/folders/{workspaceId}"
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
            url: statics.API + "/workspaces:search?offset={offset}&limit={limit}&text={text}&order_by={orderBy}"
          },
          getPageTrashed: {
            useCache: false,
            method: "GET",
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
            url: statics.API + "/services/-/resource-usages?wallet_id={walletId}&offset={offset}&limit={limit}&filters={filters}&order_by={orderBy}"
          },
          getWithWallet2: {
            method: "GET",
            url: statics.API + "/services/-/resource-usages?wallet_id={walletId}&offset={offset}&limit={limit}"
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
            method: "DELETE",
            url: statics.API + "/trash"
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
          get: {
            method: "GET",
            url: statics.API + "/projects?type=template"
          },
          getPage: {
            method: "GET",
            url: statics.API + "/projects?type=template&offset={offset}&limit={limit}"
          }
        }
      },
      /*
       * TASKS
       */
      "tasks": {
        useCache: false,
        idField: "id",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/tasks"
          }
        }
      },

      /*
       * SERVICES
       */
      "services": {
        useCache: true,
        idField: ["key", "version"],
        endpoints: {
          pricingPlans: {
            useCache: false,
            method: "GET",
            url: statics.API + "/catalog/services/{key}/{version}/pricing-plan"
          }
        }
      },

      /*
       * SERVICES V2 (web-api >=0.42.0)
       */
      "servicesV2": {
        useCache: false, // handled in osparc.store.Services
        idField: ["key", "version"],
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/catalog/services/-/latest"
          },
          getPage: {
            method: "GET",
            url: statics.API + "/catalog/services/-/latest?offset={offset}&limit={limit}"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/catalog/services/{key}/{version}"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/catalog/services/{key}/{version}"
          }
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
       * PRICING PLANS
       */
      "pricingPlans": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/admin/pricing-plans"
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
       * PRICING UNITS
       */
      "pricingUnits": {
        useCache: true,
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
          }
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
            url: statics.API + "/auth/api-keys"
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
          }
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
          }
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
      "users": {
        endpoints: {
          search: {
            method: "GET",
            url: statics.API + "/users:search?email={email}"
          },
          preRegister: {
            method: "POST",
            url: statics.API + "/users:pre-register"
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
       * CLUSTERS
       */
      "clusters": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/clusters"
          },
          post: {
            method: "POST",
            url: statics.API + "/clusters"
          },
          pingWCredentials: {
            method: "POST",
            url: statics.API + "/clusters:ping"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/clusters/{cid}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/clusters/{cid}"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/clusters/{cid}"
          },
          ping: {
            method: "POST",
            url: statics.API + "/clusters/{cid}:ping"
          }
        }
      },
      "clusterDetails": {
        useCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/clusters/{cid}/details"
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
          }
        }
      },
      /*
       * STORAGE LOCATIONS
       */
      "storageLocations": {
        useCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/storage/locations"
          }
        }
      },
      /*
       * STORAGE DATASETS
       */
      "storageDatasets": {
        useCache: false,
        endpoints: {
          getByLocation: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/datasets"
          }
        }
      },
      /*
       * STORAGE FILES
       */
      "storageFiles": {
        useCache: false,
        endpoints: {
          getByLocationAndDataset: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/datasets/{datasetId}/metadata"
          },
          getByNode: {
            method: "GET",
            url: statics.API + "/storage/locations/0/files/metadata?uuid_filter={nodeId}"
          },
          put: {
            method: "PUT",
            url: statics.API + "/storage/locations/{toLoc}/files/{fileName}?extra_location={fromLoc}&extra_source={fileUuid}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/storage/locations/{locationId}/files/{fileUuid}"
          }
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
          put: {
            method: "PATCH",
            url: statics.API + "/tags/{tagId}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/tags/{tagId}"
          }
        }
      }
    };
  },

  members: {
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

        res.addListenerOnce(endpoint + "Success", e => {
          const response = e.getRequest().getResponse();
          const endpointDef = resourceDefinition.endpoints[endpoint];
          const data = endpointDef.isJsonFile ? response : response.data;
          const useCache = ("useCache" in endpointDef) ? endpointDef.useCache : resourceDefinition.useCache;
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
        }, this);

        res.addListener(endpoint + "Error", e => {
          if (e.getPhase() === "timeout") {
            if (options.timeout && options.timeoutRetries) {
              options.timeoutRetries--;
              sendRequest();
              return;
            }
          }

          let message = null;
          let status = null;
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
                  qx.core.Init.getApplication().logout(qx.locale.Manager.tr("You were logged out. Your cookie might have expired."));
                }
              });
          }

          if ([404, 503].includes(status)) {
            message += "<br>Please try again later and/or contact support";
          }
          const err = Error(message ? message : `Error while trying to fetch ${endpoint} ${resource}`);
          if (status) {
            err.status = status;
          }
          reject(err);
        });

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
    }
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

    getCompatibleInputs: function(node1, portId1, node2) {
      const url = this.__getMatchInputsUrl(node1, portId1, node2);

      // eslint-disable-next-line no-underscore-dangle
      const cachedCPs = this.getInstance().__getCached("portsCompatibility") || {};
      const strUrl = JSON.stringify(url);
      if (strUrl in cachedCPs) {
        return Promise.resolve(cachedCPs[strUrl]);
      }
      const params = {
        url
      };
      return this.fetch("portsCompatibility", "matchInputs", params)
        .then(data => {
          cachedCPs[strUrl] = data;
          // eslint-disable-next-line no-underscore-dangle
          this.getInstance().__setCached("portsCompatibility", cachedCPs);
          return data;
        });
    },

    __getMatchInputsUrl: function(node1, portId1, node2) {
      return {
        "serviceKey2": encodeURIComponent(node2.getKey()),
        "serviceVersion2": node2.getVersion(),
        "serviceKey1": encodeURIComponent(node1.getKey()),
        "serviceVersion1": node1.getVersion(),
        "portKey1": portId1
      };
    },

    getErrorMsg: function(resp) {
      const error = resp["error"];
      return error ? error["errors"][0].message : null;
    }
  }
});

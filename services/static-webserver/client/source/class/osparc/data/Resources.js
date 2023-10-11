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
       * STUDIES
       */
      "studies": {
        useCache: true,
        idField: "uuid",
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/projects?type=user"
          },
          getPage: {
            method: "GET",
            url: statics.API + "/projects?type=user&offset={offset}&limit={limit}"
          },
          getPageFilterSearch: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects?type=user&offset={offset}&limit={limit}&search={text}"
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
          put: {
            method: "PUT",
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
          checkShareePermissions: {
            useCache: false,
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/-/services:access?for_gid={gid}"
          },
          addTag: {
            useCache: false,
            method: "PUT",
            url: statics.API + "/projects/{studyId}/tags/{tagId}"
          },
          removeTag: {
            useCache: false,
            method: "DELETE",
            url: statics.API + "/projects/{studyId}/tags/{tagId}"
          }
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
      "studyPreviews": {
        useCache: true,
        idField: "uuid",
        endpoints: {
          getPreviews: {
            method: "GET",
            url: statics.API + "/projects/{studyId}/nodes/-/preview"
          }
        }
      },
      "resourceUsage": {
        useCache: false,
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/services/-/resource-usages?offset={offset}&limit={limit}"
          }
        }
      },
      "resourceUsagePerWallet": {
        useCache: false,
        endpoints: {
          getPage: {
            method: "GET",
            url: statics.API + "/services/-/resource-usages?wallet_id={walletId}&offset={offset}&limit={limit}"
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
          },
          put: {
            method: "PUT",
            url: statics.API + "/projects/{studyId}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/projects/{studyId}"
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
          get: {
            method: "GET",
            url: statics.API + "/catalog/services"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/catalog/services/{key}/{version}"
          },
          patch: {
            method: "PATCH",
            url: statics.API + "/catalog/services/{key}/{version}"
          },
          pricingPlans: {
            useCache: false,
            method: "GET",
            url: statics.API + "/catalog/services/{key}/{version}/pricing-plan"
          }
        }
      },
      /*
       * PORT COMPATIBILITY
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
       * GROUPS/DAGS
       */
      "dags": {
        useCache: true,
        idField: "key",
        endpoints: {
          post: {
            method: "POST",
            url: statics.API + "/catalog/dags"
          },
          get: {
            method: "GET",
            url: statics.API + "/catalog/dags"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/catalog/dags/{dagId}"
          }
        }
      },
      /*
       * SCHEDULED MAINTENANCE
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
        useCache: true,
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
        useCache: false,
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
      "credits-price": {
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/credits-price"
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
      /*
       * PAYMENTS
       */
      "payments": {
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/wallets/-/payments"
          },
          startPayment: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/payments"
          },
          cancelPayment: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/payments/{paymentId}:cancel"
          }
        }
      },
      /*
       * PAYMENTS METHODS
       */
      "payments-methods": {
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
      "auto-recharge": {
        useCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/wallets/{walletId}/auto-recharge"
          },
          start: {
            method: "POST",
            url: statics.API + "/wallets/{walletId}/auto-recharge"
          },
          stop: {
            method: "DELETE",
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
          checkInvitation: {
            method: "POST",
            url: statics.API + "/auth/register/invitations:check"
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
        idField: "id",
        useCache: true,
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
     * Method to fetch resources from the server. If configured properly, the resources in the response will be cached in {osparc.store.Store}.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {String} endpoint Name of the endpoint. Several endpoints can be defined for each resource.
     * @param {Object} params Object containing the parameters for the url and for the body of the request, under the properties 'url' and 'data', respectively.
     * @param {String} deleteId When deleting, id of the element that needs to be deleted from the cache.
     * @param {Object} options Collections of options
     */
    fetch: function(resource, endpoint, params = {}, deleteId, options = {}) {
      return new Promise((resolve, reject) => {
        if (this.self().resources[resource] == null) {
          reject(Error(`Error while fetching ${resource}: the resource is not defined`));
        }

        const resourceDefinition = this.self().resources[resource];
        const res = new osparc.io.rest.Resource(resourceDefinition.endpoints);

        if (!res.includesRoute(endpoint)) {
          reject(Error(`Error while fetching ${resource}: the endpoint is not defined`));
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
            if (endpoint.includes("delete")) {
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
          "resolveWResponse" in options && options.resolveWResponse ? resolve(response) : resolve(data);
        }, this);

        res.addListenerOnce(endpoint + "Error", e => {
          let message = null;
          let status = null;
          if (e.getData().error) {
            const logs = e.getData().error.logs || null;
            if (logs && logs.length) {
              message = logs[0].message;
            }
            status = e.getData().error.status;
          } else {
            const req = e.getRequest();
            message = req.getResponse();
            status = req.getStatus();
          }
          res.dispose();
          if ([404, 503].includes(status)) {
            message += "<br>Please try again later and/or contact support";
          }
          const err = Error(message ? message : `Error while trying to fetch ${endpoint} ${resource}`);
          if (status) {
            err.status = status;
          }
          reject(err);
        });

        res[endpoint](params.url || null, params.data || null);
      });
    },

    getAllPages: function(resource, params = {}) {
      return new Promise((resolve, reject) => {
        let resources = [];
        let offset = 0;
        if (!("url" in params)) {
          params["url"] = {};
        }
        params["url"]["offset"] = offset;
        params["url"]["limit"] = 40;
        const endpoint = "getPage";
        const options = {
          resolveWResponse: true
        };
        this.fetch(resource, endpoint, params, null, options)
          .then(resp => {
            const data = resp["data"];
            const meta = resp["_meta"];
            resources = [...resources, ...data];
            const allRequests = [];
            for (let i=offset+meta.limit; i<meta.total; i+=meta.limit) {
              params.url.offset = i;
              allRequests.push(this.fetch(resource, endpoint, params));
            }
            Promise.all(allRequests)
              .then(resps => {
                resps.forEach(respData => resources = [...resources, ...respData]);
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
    get: function(resource, params, useCache = true) {
      if (useCache) {
        const stored = this.__getCached(resource);
        if (stored) {
          return Promise.resolve(stored);
        }
      }
      return this.fetch(resource, "get", params || {});
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
    fetch: function(resource, endpoint, params, deleteId, options = {}) {
      return this.getInstance().fetch(resource, endpoint, params, deleteId, options);
    },
    getOne: function(resource, params, id, useCache) {
      return this.getInstance().getOne(resource, params, id, useCache);
    },
    get: function(resource, params, useCache) {
      return this.getInstance().get(resource, params, useCache);
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

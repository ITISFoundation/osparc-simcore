/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Class that defines all the endpoints of the API to get the application resources. It also offers some convenient methods
 * to get them. It stores all the data in {osparc.store.Store} and consumes it from there whenever it is possible. The flag
 * "usesCache" must be set in the resource definition.
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
 *   osparc.data.Resources.fetch("studies", "post", params)
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
 *       usesCache: true, // Decide if the resources in the response have to be cached to avoid future calls
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
       * STUDIES
       */
      studies: {
        usesCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/projects?type=user"
          },
          getOne: {
            method: "GET",
            url: statics.API + "/projects/{project_id}"
          },
          getActive: {
            usesCache: false,
            method: "GET",
            url: statics.API + "/projects/active?client_session_id={tab_id}"
          },
          open: {
            usesCache: false,
            method: "POST",
            url: statics.API + "/projects/{project_id}:open"
          },
          close: {
            usesCache: false,
            method: "POST",
            url: statics.API + "/projects/{project_id}:close"
          },
          post: {
            method: "POST",
            url: statics.API + "/projects"
          },
          postFromTemplate: {
            method: "POST",
            url: statics.API + "/projects?from_template={template_id}"
          },
          put: {
            method: "PUT",
            url: statics.API + "/projects/{project_id}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/projects/{project_id}"
          }
        }
      },
      /*
       * TEMPLATES (actually studies flagged as templates)
       */
      templates: {
        usesCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/projects?type=template"
          },
          postToTemplate: {
            method: "POST",
            url: statics.API + "/projects?as_template={study_id}"
          },
          put: {
            method: "PUT",
            url: statics.API + "/projects/{project_id}" // FIXME: /projects/{project_id}?run={run} <<-- query is missing!!! (issue #1176)
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/projects/{project_id}"
          }
        }
      },
      /*
       * CONFIG
       */
      config: {
        usesCache: true,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/config"
          }
        }
      },
      /*
       * PROFILE
       */
      profile: {
        usesCache: true,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/me"
          }
        }
      },
      /*
       * TOKENS
       */
      tokens: {
        idField: "service",
        usesCache: true,
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
       * PASSWORD
       */
      password: {
        usesCache: false,
        endpoints: {
          post: {
            method: "POST",
            url: statics.API + "/auth/change-password"
          }
        }
      },
      /*
       * HEALTHCHECK
       */
      healthCheck: {
        usesCache: false,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/"
          }
        }
      },
      /*
       * INTERACTIVE SERVICES
       */
      interactiveServices: {
        usesCache: false,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/running_interactive_services/{nodeId}"
          },
          post: {
            method: "POST",
            url: statics.API + "/running_interactive_services?project_id={projectId}&service_uuid={nodeId}&service_key={serviceKey}&service_tag={serviceVersion}"
          },
          delete: {
            method: "DELETE",
            url: statics.API + "/running_interactive_services/{nodeId}"
          }
        }
      },
      /*
       * SERVICES (TODO: remove frontend processing. This is unusable for the moment)
       */
      servicesTodo: {
        usesCache: true,
        endpoints: {
          get: {
            method: "GET",
            url: statics.API + "/services"
          }
        }
      },
      /*
       * AUTH
       */
      auth: {
        usesCache: false,
        endpoints: {
          postLogin: {
            method: "POST",
            url: statics.API + "/auth/login"
          },
          getLogout: {
            method: "GET",
            url: statics.API + "/auth/logout"
          },
          postRegister: {
            method: "POST",
            url: statics.API + "/auth/register"
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
      storageLocations: {
        usesCache: true,
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
      storageDatasets: {
        usesCache: false,
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
      storageFiles: {
        usesCache: false,
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
            url:  statics.API + "/storage/locations/{locationId}/files/{fileUuid}"
          }
        }
      },
      /*
       * STORAGE LINK
       */
      storageLink: {
        usesCache: false,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/storage/locations/{locationId}/files/{fileUuid}"
          },
          put: {
            method: "PUT",
            url: statics.API + "/storage/locations/{locationId}/files/{fileUuid}"
          }
        }
      },
      /*
       * ACTIVITY
       */
      activity: {
        usesCache: false,
        endpoints: {
          getOne: {
            method: "GET",
            url: statics.API + "/activity/status"
          }
        }
      },

      /*
       * Test/Diagnonstic entrypoint
       */
      checkEP: {
        usesCache: false,
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
     */
    fetch: function(resource, endpoint, params = {}, deleteId) {
      return new Promise((resolve, reject) => {
        if (this.self().resources[resource] == null) { // eslint-disable-line no-eq-null
          reject(Error(`Error while fetching ${resource}: the resource is not defined`));
        }

        const resourceDefinition = this.self().resources[resource];
        const res = new osparc.io.rest.Resource(resourceDefinition.endpoints);

        if (!res.includesRoute(endpoint)) { // eslint-disable-line no-eq-null
          reject(Error(`Error while fetching ${resource}: the endpoint is not defined`));
        }

        res.addListenerOnce(endpoint + "Success", e => {
          const data = e.getRequest().getResponse().data;
          const endpointDef = resourceDefinition.endpoints[endpoint];
          const useCache = ("usesCache" in endpointDef) ? endpointDef.useCache : resourceDefinition.usesCache;
          if (useCache) {
            if (endpoint.includes("delete")) {
              this.__removeCached(resource, deleteId);
            } else {
              this.__setCached(resource, data);
            }
          }
          res.dispose();
          resolve(data);
        }, this);

        res.addListenerOnce(endpoint + "Error", e => {
          let message = null;
          if (e.getData().error) {
            const logs = e.getData().error.logs || null;
            if (logs && logs.length) {
              message = logs[0].message;
            }
          }
          res.dispose();
          reject(Error(message ? message : `Error while fetching ${resource}`));
        });

        res[endpoint](params.url || null, params.data || null);
      });
    },

    /**
     * Get a single resource or a specific resource inside a collection.
     * @param {String} resource Name of the resource as defined in the static property 'resources'.
     * @param {Object} params Object containing the parameters for the url and for the body of the request, under the properties 'url' and 'data', respectively.
     * @param {String} id Id of the element to get, if it is a collection of elements.
     * @param {Boolean} useCache Whether the cache has to be used. If false, an API call will be issued.
     */
    getOne: function(resource, params, id, useCache = true) {
      if (useCache) {
        const stored = this.__getCached(resource);
        if (stored) {
          const idField = this.self().resources[resource].idField || "uuid";
          const item = Array.isArray(stored) ? stored.find(element => element[idField] === id) : stored;
          if (item) {
            console.log(`Getting ${resource} from cache.`);
            return Promise.resolve(item);
          }
        }
        console.log(`Fetching ${resource} from server.`);
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
          console.log(`Getting all ${resource} from cache.`);
          return Promise.resolve(stored);
        }
        console.log(`Fetching ${resource} from server.`);
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
      const store = osparc.store.Store.getInstance();
      switch (resource) {
        default:
          store.update(resource, data, this.self().resources[resource].idField || "uuid");
      }
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
    fetch: function(resource, endpoint, params, deleteId) {
      return this.getInstance().fetch(resource, endpoint, params, deleteId);
    },
    getOne: function(resource, params, id, useCache) {
      return this.getInstance().getOne(resource, params, id, useCache);
    },
    get: function(resource, params, useCache) {
      return this.getInstance().get(resource, params, useCache);
    }
  }
});

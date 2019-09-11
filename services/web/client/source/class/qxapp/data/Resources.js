/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.data.Resources", {
  extend: qx.core.Object,

  type: "singleton",

  defer: function(statics) {
    statics.resources = {
      studies: new qx.io.rest.Resource({
        get: {
          method: "GET",
          url: statics.API + "/projects?type=user"
        },
        getOne: {
          method: "GET",
          url: statics.API + "/projects/{project_id}"
        },
        post: {
          method: "POST",
          url: statics.API + "/projects"
        },
        postFromTemplate: {
          method: "POST",
          url: statics.API + "/projects?from_template={template_id}"
        },
        postToTemplate: {
          method: "POST",
          url: statics.API + "/projects?as_template={study_id}"
        },
        put: {
          method: "PUT",
          url: statics.API + "/projects/{project_id}"
        },
        delete: {
          method: "DELETE",
          url: statics.API + "/projects/{project_id}"
        }
      }),
      templates: new qx.io.rest.Resource({
        get: {
          method: "GET",
          url: statics.API + "/projects?type=template"
        }
      })
    };
  },

  members: {
    fetch: function(resource, method = "GET", useCache = true) {
      return new Promise((resolve, reject) => {
        if (this.self().resources[resource] == null) {
          reject(Error(`Error while fetching ${resource}: the resource is not defined`));
        }
        const stored = this.__getCached(resource);
        if (!useCache || !stored) {
          // Fetch resources
          const call = this.self().resources[resource];
          const normalizedMethod = method.trim().toLowerCase();

          call.addListenerOnce(normalizedMethod + "Success", e => {
            const data = e.getRequest().getResponse().data;
            this.__setCached(resource, data);
            resolve(data);
          }, this);

          call.addListenerOnce(normalizedMethod + "Error", e => reject(Error(`Error while fetching ${resource}: ${e.getData()}`)));

          call[normalizedMethod]();
        } else {
          // Using cache
          resolve(stored);
        }
      });
    },

    get: function(resource, useCache = true) {
      return this.fetch(resource, "GET", useCache);
    },

    post: function(resource, useCache = true) {
      return this.fetch(resource, "POST", useCache);
    },

    put: function(resource, useCache = true) {
      return this.fetch(resource, "PUT", useCache);
    },

    delete: function(resource, useCache = true) {
      return this.fetch(resource, "DELETE", useCache);
    },

    __getCached: function(resource) {
      const stored = qxapp.store.Store.getInstance().get(resource);
      switch (resource) {
        case "studies":
          if (stored.length === 0) {
            return null;
          }
          break;
      }
      return stored;
    },

    __setCached: function(resource, data) {
      const store = qxapp.store.Store.getInstance();
      switch (resource) {
        default:
          store.set(resource, data);
      }
    }
  },

  statics: {
    API: "/v0",
    fetch: function(resource, method, useCache) {
      return this.getInstance().fetch(resource, method, useCache);
    },
    get: function(resource, useCache) {
      return this.getInstance().get(resource, useCache);
    },
    post: function(resource, useCache) {
      return this.getInstance().post(resource, useCache);
    },
    put: function(resource, useCache) {
      return this.getInstance().put(resource, useCache);
    },
    delete: function(resource, useCache) {
      return this.getInstance().delete(resource, useCache);
    }
  }
});

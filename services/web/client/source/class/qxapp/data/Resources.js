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
      /*
       * STUDIES
       */
      studies: new qxapp.io.rest.Resource({
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
      /*
       * TEMPLATES (actually studies flagged as studies)
       */
      templates: new qxapp.io.rest.Resource({
        get: {
          method: "GET",
          url: statics.API + "/projects?type=template"
        }
      })
    };
  },

  members: {
    fetch: function(resource, endpoint, params = {}, useCache = false) {
      return new Promise((resolve, reject) => {
        if (this.self().resources[resource] == null) {
          reject(Error(`Error while fetching ${resource}: the resource is not defined`));
        } else if (this.self().resources[resource][endpoint] == null) {
          reject(Error(`Error while fetching ${resource}: the endpoint is not defined`));
        }
        const stored = this.__getCached(resource);
        if (!useCache || !stored) {
          // Fetch resources
          const call = this.self().resources[resource];

          call.addListenerOnce(endpoint + "Success", e => {
            const data = e.getRequest().getResponse().data;
            this.__setCached(resource, data);
            resolve(data);
          }, this);

          call.addListenerOnce(endpoint + "Error", e => reject(Error(`Error while fetching ${resource}: ${e.getData()}`)));

          call[endpoint](params.url || null, params.data || null);
        } else {
          // Using cache
          resolve(stored);
        }
      });
    },

    getOne: function(resource, params, id, useCache = true) {
      const stored = this.__getCached(resource);
      if (stored && useCache) {
        const item = stored.find(element => element.uuid === id);
        if (item) {
          return Promise.resolve(item);
        }
      }
      return this.fetch(resource, "getOne", params, useCache)
    },

    getAll: function(resource, params, useCache = true) {
      const stored = this.__getCached(resource);
      if (stored && useCache) {
        return Promise.resolve(stored);
      } else {
        return this.fetch(resource, "get", params, useCache);
      }
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
          store.update(resource, data);
      }
    }
  },

  statics: {
    API: "/v0",
    fetch: function(resource, method, useCache) {
      return this.getInstance().fetch(resource, method, useCache);
    },
    getOne: function(resource, params, id, useCache) {
      return this.getInstance().getOne(resource, params, id, useCache);
    },

    getAll: function(resource, params, useCache) {
      return this.getInstance().getAll(resource, params, useCache);
    }
  }
});

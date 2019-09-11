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
        }
      })
    };
  },

  members: {
    fetch: function(resource, method = "GET", useCache = true) {
      return new Promise((resolve, reject) => {
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
          call.addListenerOnce(normalizedMethod + "Error", e => reject(Error(e)));
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

    __getCached: function(resource) {
      const stored = qxapp.store.Store.getInstance().get(resource);
      switch (resource) {
        case "studies":
          if (stored.length > 0) {
            return stored;
          }
          break;
      }
      return null;
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
    }
  }
});

/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2019 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("qxapp.data.Resources", {
  extend: qx.core.Object,

  type: "singleton",

  members: {
    fetch: function(resource, method = "GET", useCache = true) {
      const getter = qxapp.store.Store[this.__getterName(resource)];
      return new Promise((resolve, reject) => {
        if (!useCache || !getter()) {
          // Fetch resources
          const call = this.self()[resource];
          const normalizedMethod = method.trim().toLowerCase();
          call.addListenerOnce(normalizedMethod + "Success", e => resolve(e.getRequest().getResponse().data));
          call.addListenerOnce(normalizedMethod + "Error", e => reject(Error(e)));
          call[normalizedMethod]();
        } else {
          // Using cache
          resolve(getter());
        }
      });
    },

    get: function(resource, useCache = true) {
      return this.fetch(resource, "GET", useCache);
    },

    __getterName: function(resource) {
      return "get" + qxapp.utils.Utils.capitalize(resource);
    }
  },

  statics: {
    API: "/v0",
    studies: new qx.io.rest.Resource({
      get: {
        method: "GET",
        url: this.self().API + "/projects?type=user"
      }
    })
  },
});

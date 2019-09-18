/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Singleton class that is used as entrypoint to the webserver.
 *
 * All data transfer communication goes through the qxapp.store.Store.
 *
 * *Example*
 *
 * Here is a little example of how to use the class.
 *
 * <pre class='javascript'>
 *   let services = qxapp.store.Store.getInstance().getServices();
 * </pre>
 */

qx.Class.define("qxapp.store.Store", {
  extend: qx.core.Object,

  type : "singleton",

  properties: {
    studies: {
      check: "Array",
      init: []
    },
    config: {
      check: "Object",
      init: {}
    },
    templates: {
      check: "Array",
      init: []
    },
    profile: {
      check: "Object",
      init: {}
    },
    tokens: {
      check: "Array",
      init: []
    },
    servicesTodo: {
      check: "Array",
      init: []
    }
  },

  events: {
    "servicesRegistered": "qx.event.type.Data"
  },

  members: {
    update: function(resource, data, idField = "uuid") {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        if (Array.isArray(data)) {
          this.set(resource, data);
        } else {
          let element = stored.find(item => item[idField] === data[idField]);
          if (element) {
            const newStored = stored.map(item => {
              if (item[idField] === data[idField]) {
                return data;
              }
              return item;
            });
            this.set(resource, newStored);
          } else {
            stored.push(data);
          }
        }
      } else {
        this.set(resource, data);
      }
    },

    remove: function(resource, idField = "uuid", id) {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        const item = stored.find(element => element[idField] === id);
        if (item) {
          const index = stored.indexOf(item);
          stored.splice(index, 1);
        }
      } else if (stored[idField] && stored[idField] === id) {
        this.set(resource, {});
      }
    },

    getServices: function(reload) {
      if (!qxapp.utils.Services.reloadingServices && (reload || Object.keys(qxapp.utils.Services.servicesCached).length === 0)) {
        qxapp.utils.Services.reloadingServices = true;
        qxapp.data.Resources.get("servicesTodo")
          .then(data => {
            const allServices = data.concat(qxapp.utils.Services.getBuiltInServices());
            const filteredServices = qxapp.utils.Services.filterOutUnavailableGroups(allServices);
            const services = qxapp.utils.Services.convertArrayToObject(filteredServices);
            qxapp.utils.Services.servicesToCache(services, true);
            this.fireDataEvent("servicesRegistered", {
              services,
              fromServer: true
            });
          })
          .catch(err => {
            console.error("getServices failed", err);
            const allServices = qxapp.dev.fake.Data.getFakeServices().concat(qxapp.utils.Services.getBuiltInServices());
            const filteredServices = qxapp.utils.Services.filterOutUnavailableGroups(allServices);
            const services = qxapp.utils.Services.convertArrayToObject(filteredServices);
            qxapp.utils.Services.servicesToCache(services, false);
            this.fireDataEvent("servicesRegistered", {
              services,
              fromServer: false
            });
          });
        return null;
      }
      return qxapp.utils.Services.servicesCached;
    }
  }
});

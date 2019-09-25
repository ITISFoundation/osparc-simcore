/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Singleton class that stores all the application resources and acts as a cache for them. It is used by {qxapp.data.Resources},
 * before making an API call to retrieve resources from the server, it will try to get them from here. Same with post and put calls,
 * their stored elements will be cached here.
 *
 * *Example*
 *
 * Here is a little example of how to use the class. You can get resources like this:
 *
 * <pre class='javascript'>
 *   let studies = qxapp.store.Store.getInstance().getStudies();
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
    },
    storageLocations: {
      check: "Array",
      init: []
    }
  },

  events: {
    "servicesRegistered": "qx.event.type.Data"
  },

  members: {
    /**
     * Updates an element or a set of elements in the store.
     * @param {String} resource Name of the resource property. If used with {qxapp.data.Resources}, it has to be the same there.
     * @param {*} data Data to be stored, it needs to have the correct type as in the property definition.
     * @param {String} idField Key used for the id field. This field has to be unique among all elements of that resource.
     */
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

    /**
     * Remove an element from an array, or erase the store for a given resource.
     * @param {String} resource Name of the resource property. If used with {qxapp.data.Resources}, it has to be the same there.
     * @param {String} idField Key used for the id field. This field has to be unique among all elements of that resource.
     * @param {String} id Value of the id field.
     */
    remove: function(resource, idField = "uuid", id) {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        const item = stored.find(element => element[idField] === id);
        if (item) {
          const index = stored.indexOf(item);
          stored.splice(index, 1);
        }
      } else {
        this.set(resource, {});
      }
    },

    /**
     * This functions does the needed processing in order to have a working list of services. Could use a refactor.
     * @param {Boolean} reload ?
     */
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

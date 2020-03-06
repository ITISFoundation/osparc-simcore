/* ************************************************************************

   osparc - the simcore frontend

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
 * Singleton class that stores all the application resources and acts as a cache for them. It is used by {osparc.data.Resources},
 * before making an API call to retrieve resources from the server, it will try to get them from here. Same with post and put calls,
 * their stored elements will be cached here.
 *
 * *Example*
 *
 * Here is a little example of how to use the class. You can get resources like this:
 *
 * <pre class='javascript'>
 *   let studies = osparc.store.Store.getInstance().getStudies();
 * </pre>
 *
 * To invalidate the cache for any of the entities, config for example, just do:
 * <pre class="javascript">
 *   osparc.store.Store.getInstance().resetConfig();
 * </pre>
 * or
 * <pre class="javascript">
 *   osparc.store.Store.getInstance().invalidate("config");
 * </pre>
 * To invalidate the entire cache:
 * <pre class="javascript">
 *   osparc.store.Store.getInstance().invalidate();
 * </pre>
 */
qx.Class.define("osparc.store.Store", {
  extend: qx.core.Object,
  type : "singleton",

  properties: {
    currentStudy: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: true
    },
    currentStudyId: {
      check: "String",
      init: null,
      nullable: true
    },
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
    },
    shareStudy: {
      check: "Object",
      init: {}
    },
    tags: {
      check: "Array",
      init: [],
      event: "changeTags"
    }
  },

  events: {
    "servicesRegistered": "qx.event.type.Data"
  },

  members: {
    /**
     * Updates an element or a set of elements in the store.
     * @param {String} resource Name of the resource property. If used with {osparc.data.Resources}, it has to be the same there.
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
            this.set(resource, [...stored, data]);
          }
        }
      } else {
        this.set(resource, data);
      }
    },

    /**
     * Remove an element from an array, or erase the store for a given resource.
     * @param {String} resource Name of the resource property. If used with {osparc.data.Resources}, it has to be the same there.
     * @param {String} idField Key used for the id field. This field has to be unique among all elements of that resource.
     * @param {String} id Value of the id field.
     */
    remove: function(resource, idField = "uuid", id) {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        const item = stored.find(element => element[idField] === id);
        if (item) {
          const index = stored.indexOf(item);
          this.set(resource, [...stored.slice(0, index), ...stored.slice(index + 1)]);
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
      if (!osparc.utils.Services.reloadingServices && (reload || Object.keys(osparc.utils.Services.servicesCached).length === 0)) {
        osparc.utils.Services.reloadingServices = true;
        osparc.data.Resources.get("servicesTodo", null, !reload)
          .then(data => {
            const allServices = data.concat(osparc.utils.Services.getBuiltInServices());
            const filteredServices = osparc.utils.Services.filterOutUnavailableGroups(allServices);
            const services = osparc.utils.Services.convertArrayToObject(filteredServices);
            osparc.utils.Services.servicesToCache(services, true);
            this.fireDataEvent("servicesRegistered", {
              services,
              fromServer: true
            });
          })
          .catch(err => {
            console.error("getServices failed", err);
            const allServices = osparc.dev.fake.Data.getFakeServices().concat(osparc.utils.Services.getBuiltInServices());
            const filteredServices = osparc.utils.Services.filterOutUnavailableGroups(allServices);
            const services = osparc.utils.Services.convertArrayToObject(filteredServices);
            osparc.utils.Services.servicesToCache(services, false);
            this.fireDataEvent("servicesRegistered", {
              services,
              fromServer: false
            });
          });
        return null;
      }
      return osparc.utils.Services.servicesCached;
    },

    /**
     * Invalidates the cache for the given resources.
     * If resource is a string, it will invalidate that resource.
     * If it is an array, it will try to invalidate every resource in the array.
     * If it is not provided, it will invalidate all resources.
     *
     * @param {(string|string[])} [resources] Property or array of property names that must be reset
     */
    invalidate: function(resources) {
      if (typeof resources === "string" || resources instanceof String) {
        this.reset(resources);
      } else {
        let propertyArray;
        if (resources == null) { // eslint-disable-line no-eq-null
          propertyArray = Object.keys(qx.util.PropertyUtil.getProperties(osparc.store.Store));
        } else if (Array.isArray(resources)) {
          propertyArray = resources;
        }
        propertyArray.forEach(propName => this.reset(propName));
      }
    },

    _applyStudy: function(newStudy) {
      if (newStudy) {
        this.setCurrentStudyId(newStudy.getStudyId());
      } else {
        this.setCurrentStudyId(null);
      }
    }
  }
});

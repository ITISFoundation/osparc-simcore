/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *   Collection of methods for dealing with services data type convertions, extract
 * specific information.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let latestSrv = osparc.utils.Services.getLatest(services, serviceKey);
 * </pre>
 */

qx.Class.define("osparc.utils.Services", {
  type: "static",

  statics: {
    getTypes: function() {
      return [
        "computational",
        "dynamic"
      ];
    },

    getCategories: function() {
      return [
        "data",
        "modeling",
        "simulator",
        "solver",
        "postpro",
        "notebook"
      ];
    },

    convertArrayToObject: function(servicesArray) {
      let services = {};
      for (let i = 0; i < servicesArray.length; i++) {
        const service = servicesArray[i];
        if (!Object.prototype.hasOwnProperty.call(services, service.key)) {
          services[service.key] = {};
        }
        if (!Object.prototype.hasOwnProperty.call(services[service.key], service.version)) {
          services[service.key][service.version] = {};
        }
        services[service.key][service.version] = service;
      }
      return services;
    },

    convertObjectToArray: function(servicesObject) {
      let services = [];
      for (const serviceKey in servicesObject) {
        const serviceVersions = servicesObject[serviceKey];
        for (const serviceVersion in serviceVersions) {
          services.push(serviceVersions[serviceVersion]);
        }
      }
      return services;
    },

    getFromObject: function(services, key, version) {
      if (key in services) {
        const serviceVersions = services[key];
        if (version in serviceVersions) {
          return serviceVersions[version];
        }
      }
      return null;
    },

    getFromArray: function(services, key, version) {
      for (let i=0; i<services.length; i++) {
        if (services[i].key === key && services[i].version === version) {
          return services[i];
        }
      }
      return null;
    },

    getVersions: function(services, key) {
      let versions = [];
      if (key in services) {
        const serviceVersions = services[key];
        versions = versions.concat(Object.keys(serviceVersions));
        versions.sort(osparc.utils.Utils.compareVersionNumbers);
      }
      return versions;
    },

    getLatest: function(services, key) {
      if (key in services) {
        const versions = osparc.utils.Services.getVersions(services, key);
        return services[key][versions[versions.length - 1]];
      }
      return null;
    },

    isServiceInList: function(listOfServices, serveiceKey) {
      for (let i=0; i<listOfServices.length; i++) {
        if (listOfServices[i].key === serveiceKey) {
          return true;
        }
      }
      return false;
    },

    filterOutUnavailableGroups: function(listOfServices) {
      const filteredServices = [];
      for (let i=0; i<listOfServices.length; i++) {
        const service = listOfServices[i];
        if ("innerNodes" in service) {
          let allIn = true;
          const innerServices = service["innerNodes"];
          for (const innerService in innerServices) {
            allIn &= osparc.utils.Services.isServiceInList(listOfServices, innerServices[innerService].key);
          }
          if (allIn) {
            filteredServices.push(service);
          }
        } else {
          filteredServices.push(service);
        }
      }
      return filteredServices;
    }
  }
});

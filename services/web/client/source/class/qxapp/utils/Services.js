/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("qxapp.utils.Services", {
  type: "static",

  statics: {
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
        versions.sort(qxapp.utils.Utils.compareVersionNumbers);
      }
      return versions;
    },

    getLatest: function(services, key) {
      if (key in services) {
        const versions = qxapp.utils.Services.getVersions(services, key);
        return services[key][versions[versions.length - 1]];
      }
      return null;
    },

    getTagsOrder: function() {
      return [
        "key",
        "version",
        "type",
        "name",
        "description",
        "authors",
        "contact",
        "inputs",
        "outputs"
      ];
    },

    tagDescriptiontoString: function(tagDescription) {
      return JSON.stringify(tagDescription, null, 2);
      /*
      let descStr = "";
      if (Array.isArray(tagDescription)) {
        continue;
      } else if (tagDescription instanceof Object) {
        continue;
      }
      descStr = tagDescription;
      return descStr;
      */
    }
  }
});

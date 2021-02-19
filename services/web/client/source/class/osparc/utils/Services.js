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
    TYPES: {
      computational: {
        label: "Computational",
        icon: "@FontAwesome5Solid/cogs/"
      },
      dynamic: {
        label: "Interactive",
        icon: "@FontAwesome5Solid/mouse-pointer/"
      },
      container: {
        label: "Group of nodes",
        icon: "@FontAwesome5Solid/box-open/"
      }
    },

    servicesCached: {},

    getTypes: function() {
      return Object.keys(this.TYPES);
    },

    getType: function(type) {
      return this.TYPES[type.trim().toLowerCase()];
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
        const versions = this.getVersions(services, key);
        return services[key][versions[versions.length - 1]];
      }
      return null;
    },

    getMetaData: function(key, version) {
      let metaData = null;
      if (key && version) {
        const services = osparc.utils.Services.servicesCached;
        metaData = this.getFromObject(services, key, version);
        if (metaData) {
          metaData = osparc.utils.Utils.deepCloneObject(metaData);
          return metaData;
        }
      }
      return null;
    },

    getFilePicker: function() {
      return this.self().getLatest(this.servicesCached, "simcore/services/frontend/file-picker");
    },

    getNodesGroup: function() {
      return this.self().getLatest(this.servicesCached, "simcore/services/frontend/nodes-group");
    },

    addServiceToCache: function(service) {
      this.servicesCached = Object.assign(this.servicesCached, service);
    },

    servicesToCache: function(services) {
      this.servicesCached = {};
      this.__addExtraInfo(services);
      this.servicesCached = Object.assign(this.servicesCached, services);
    },

    __addExtraInfo: function(services) {
      Object.values(services).forEach(serviceWVersion => {
        Object.values(serviceWVersion).forEach(service => {
          if (osparc.data.model.Node.isComputational(service)) {
            osparc.component.metadata.Quality.attachQualityToObject(service);
          }
        });
      });
    },

    getUniqueServicesFromWorkbench: function(workbench) {
      const services = [];
      Object.values(workbench).forEach(node => {
        const service = {
          key: node["key"],
          version: node["version"]
        };
        const idx = services.indexOf(existingSrv => existingSrv.key === service.key && existingSrv.version === service.version);
        if (idx === -1) {
          services.push(service);
        }
      });
      return services;
    }
  }
});

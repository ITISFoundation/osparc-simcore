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

/**
 *   Collection of methods for dealing with services data type convertions, extract
 * specific information.
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let latestSrv = qxapp.utils.Services.getLatest(services, serviceKey);
 * </pre>
 */

qx.Class.define("qxapp.utils.Services", {
  type: "static",

  statics: {

    CATEGORIES: {
      postpro: {
        label: "Postpro",
        icon: "@FontAwesome5Solid/chart-bar/"
      },
      notebook: {
        label: "Notebook",
        icon: "@FontAwesome5Solid/file-code/"
      },
      solver: {
        label: "Solver",
        icon: "@FontAwesome5Solid/calculator/"
      },
      simulator: {
        label: "Simulator",
        icon: "@FontAwesome5Solid/brain/"
      },
      modeling: {
        label: "Modeling",
        icon: "@FontAwesome5Solid/cube/"
      },
      data: {
        label: "Data",
        icon: "@FontAwesome5Solid/file/"
      }
    },

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

    getTypes: function() {
      return Object.keys(this.TYPES);
    },

    getCategories: function() {
      return Object.keys(this.CATEGORIES);
    },

    getCategory: function(category) {
      return this.CATEGORIES[category.trim().toLowerCase()];
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
            allIn &= qxapp.utils.Services.isServiceInList(listOfServices, innerServices[innerService].key);
          }
          if (allIn) {
            filteredServices.push(service);
          }
        } else {
          filteredServices.push(service);
        }
      }
      return filteredServices;
    },

    __matchPortType: function(typeA, typeB) {
      if (typeA === typeB) {
        return true;
      }
      let mtA = qxapp.data.MimeType.getMimeType(typeA);
      let mtB = qxapp.data.MimeType.getMimeType(typeB);
      return mtA && mtB &&
        new qxapp.data.MimeType(mtA).match(new qxapp.data.MimeType(mtB));
    },

    areNodesCompatible: function(topLevelPort1, topLevelPort2) {
      console.log("areNodesCompatible", topLevelPort1, topLevelPort2);
      return topLevelPort1.isInput !== topLevelPort2.isInput;
    },

    arePortsCompatible: function(port1, port2) {
      return port1.type && port2.type && this.__matchPortType(port1.type, port2.type);
    },

    getNodeMetaData: function(key, version) {
      let metaData = null;
      if (key && version) {
        metaData = qxapp.utils.Services.getFromObject(qxapp.store.Store.getInstance().getServices(), key, version);
        if (metaData) {
          metaData = qxapp.utils.Utils.deepCloneObject(metaData);
          if (metaData.key === "simcore/services/dynamic/modeler/webserver") {
            metaData.outputs["modeler"] = {
              "label": "Modeler",
              "displayOrder":0,
              "description": "Modeler",
              "type": "node-output-tree-api-v0.0.1"
            };
            delete metaData.outputs["output_1"];
          }
          return metaData;
        }
        const allServices = qxapp.dev.fake.Data.getFakeServices().concat(this.getBuiltInServices());
        metaData = qxapp.utils.Services.getFromArray(allServices, key, version);
        if (metaData) {
          return qxapp.utils.Utils.deepCloneObject(metaData);
        }
      }
      return null;
    },

    getBuiltInServices: function() {
      const builtInServices = [{
        key: "simcore/services/frontend/file-picker",
        version: "1.0.0",
        type: "dynamic",
        name: "File Picker",
        description: "File Picker",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.ethz.ch"
        }],
        contact: "maiz@itis.ethz.ch",
        inputs: {},
        outputs: {
          outFile: {
            displayOrder: 0,
            label: "File",
            description: "Chosen File",
            type: "data:*/*"
          }
        }
      }];
      return builtInServices;
    }
  }
});

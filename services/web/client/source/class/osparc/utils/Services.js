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

    servicesCached: {},

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

    isServiceInList: function(listOfServices, serveiceKey) {
      for (let i=0; i<listOfServices.length; i++) {
        if (listOfServices[i].key === serveiceKey) {
          return true;
        }
      }
      return false;
    },

    getNodeMetaData: function(key, version) {
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
      return {
        key: "simcore/services/frontend/file-picker",
        version: "1.0.0",
        type: "dynamic",
        name: "File Picker",
        description: "File Picker",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.swiss"
        }],
        contact: "maiz@itis.swiss",
        inputs: {},
        outputs: {
          outFile: {
            displayOrder: 0,
            label: "File",
            description: "Chosen File",
            type: "data:*/*"
          }
        }
      };
    },

    getNodesGroup: function() {
      return {
        key: "simcore/services/frontend/nodes-group",
        version: "1.0.0",
        type: "group",
        name: "Group",
        description: "Group of nodes",
        authors: [{
          name: "Odei Maiz",
          email: "maiz@itis.swiss"
        }],
        contact: "maiz@itis.swiss",
        inputs: {},
        outputs: {}
      };
    },

    getBuiltInServices: function() {
      const builtInServices = [
        this.getFilePicker(),
        this.getNodesGroup()
      ];
      return builtInServices;
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
      const categories = this.__getCategories();
      const classifiers = this.__getClassifiers();
      Object.values(services).forEach(serviceWVersion => {
        Object.values(serviceWVersion).forEach(service => {
          service["uuid"] = service["key"];
          service["prjOwner"] = service["contact"];
          service["thumbnail"] = service["thumbnail"] || "@FontAwesome5Solid/paw/50";
          service["accessRights"] = {
            "1": {
              "read": true,
              "write": true,
              "delete": false
            }
          };
          if (Object.prototype.hasOwnProperty.call(categories, service["key"])) {
            service["category"] = categories[service["key"]]["category"];
          } else {
            service["category"] = "Unknown";
          }
          if (Object.prototype.hasOwnProperty.call(classifiers, service["key"])) {
            service["classifiers"] = classifiers[service["key"]]["classifiers"];
          } else {
            service["classifiers"] = [];
          }
        });
      });
    },

    __getCategories: function() {
      return {
        "simcore/services/frontend/file-picker": {
          "category": "Data"
        },
        "simcore/services/dynamic/mattward-viewer": {
          "category": "Solver"
        },
        "simcore/services/dynamic/bornstein-viewer": {
          "category": "Solver"
        },
        "simcore/services/dynamic/cc-0d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/cc-1d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/cc-2d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/raw-graphs": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/3d-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/3d-viewer-gpu": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/jupyter-r-notebook": {
          "category": "Notebook"
        },
        "simcore/services/dynamic/jupyter-base-notebook": {
          "category": "Notebook"
        },
        "simcore/services/dynamic/jupyter-scipy-notebook": {
          "category": "Notebook"
        },
        "simcore/services/comp/rabbit-ss-0d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/rabbit-ss-1d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/rabbit-ss-2d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/human-gb-0d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/human-gb-1d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/human-gb-2d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/human-ord-0d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/human-ord-1d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/human-ord-2d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/osparc-opencor": {
          "category": "Solver"
        },

        "simcore/services/comp/itis/sleeper": {
          "category": "Solver"
        },
        "simcore/services/comp/itis/isolve-emlf": {
          "category": "Solver"
        },
        "simcore/services/comp/itis/neuron-isolve": {
          "category": "Solver"
        },
        "simcore/services/comp/ucdavis-singlecell-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/ucdavis-1d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/ucdavis-2d-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/comp/kember-cardiac-model": {
          "category": "Solver"
        },
        "simcore/services/demodec/computational/itis/Solver-LF": {
          "category": "Solver"
        },
        "simcore/services/demodec/container/itis/s4l/Simulator/LF": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/MaterialDB": {
          "category": "Solver"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Modeler": {
          "category": "Modeling"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Boundary": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Grid": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Materials": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Sensors": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Setup": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/SolverSettings": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/LF/Voxel": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/NetworkConnection": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Neurons": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/PointProcesses": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Sensors": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Setup": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/SolverSettings": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/Simulator/Neuron/Sources": {
          "category": "Simulator"
        },
        "simcore/services/demodec/dynamic/itis/s4l/StimulationSelectivity": {
          "category": "PostPro"
        },
        "simcore/services/demodec/dynamic/itis/s4l/neuroman": {
          "category": "Modeling"
        },
        "simcore/services/dynamic/kember-viewer": {
          "category": "PostPro"
        },
        "simcore/services/dynamic/modeler/webserver": {
          "category": "Modeling"
        },
        "simcore/services/dynamic/modeler/webserverwithrat": {
          "category": "Modeling"
        },
        "simcore/services/frontend/multi-plot": {
          "category": "PostPro"
        }
      };
    },

    __getClassifiers: function() {
      return {
        "simcore/services/comp/isolve": {
          "classifiers": [
            "topics::z43::s4l",
            "company::z43::itis"
          ]
        },
        "simcore/services/comp/ti-solutions-optimizer": {
          "classifiers": [
            "company::z43::tisolutions"
          ]
        },
        "simcore/services/dynamic/electrode-selector": {
          "classifiers": [
            "company::z43::tisolutions"
          ]
        },
        "simcore/services/dynamic/jupyter-base-notebook": {
          "classifiers": [
            "topics::jupyter-notebook",
            "company::z43::itis"
          ]
        },
        "simcore/services/dynamic/jupyter-neuron": {
          "classifiers": [
            "topics::python",
            "topics::jupyter-notebook",
            "company::z43::itis"
          ]
        },
        "simcore/services/dynamic/jupyter-octave": {
          "classifiers": [
            "topics::jupyter-notebook",
            "topics::octave",
            "company::z43::itis"
          ]
        },
        "simcore/services/dynamic/jupyter-octave-python-math": {
          "classifiers": [
            "topics::jupyter-notebook",
            "topics::octave",
            "company::z43::itis"
          ]
        },
        "simcore/services/dynamic/jupyter-scipy-notebook": {
          "classifiers": [
            "topics::python",
            "topics::jupyter-notebook",
            "company::z43::itis"
          ]
        },
        "simcore/services/dynamic/jupyter-smash": {
          "classifiers": [
            "topics::python",
            "topics::jupyter-notebook",
            "topics::z43::s4l",
            "company::z43::itis"
          ]
        },
        "simcore/services/dynamic/osparc-lab": {
          "classifiers": [
            "topics::python",
            "topics::jupyter-notebook",
            "company::z43::itis"
          ]
        },
        "simcore/services/dynamic/tissue-properties": {
          "classifiers": [
            "company::z43::itis"
          ]
        }
      };
    }
  }
});

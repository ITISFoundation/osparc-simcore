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

  construct: function() {
    this.__reloadingServices = false;
    this.__servicesCached = {};
  },

  events: {
    "servicesRegistered": "qx.event.type.Data"
  },

  properties: {
    studies: {
      check: "Array",
      init: []
    }
  },

  members: {
    __reloadingServices: null,
    __servicesCached: null,

    update: function(resource, data) {
      const stored = this.get(resource);
      if (Array.isArray(stored)) {
        if (Array.isArray(data)) {
          this.set(resource, data);
        } else {
          let item = stored.find(item => item.uuid === data.uuid);
          if (item) {
            const newStored = stored.map(item => {
              if (item.uuid === data.uuid) {
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

    getServices: function(reload) {
      if (!this.__reloadingServices && (reload || Object.keys(this.__servicesCached).length === 0)) {
        this.__reloadingServices = true;
        let req = new qxapp.io.request.ApiRequest("/services", "GET");
        req.addListener("success", e => {
          let requ = e.getTarget();
          const {
            data
          } = requ.getResponse();
          const allServices = data.concat(qxapp.utils.Services.getBuiltInServices());
          const filteredServices = qxapp.utils.Services.filterOutUnavailableGroups(allServices);
          const services = qxapp.utils.Services.convertArrayToObject(filteredServices);
          this.__servicesToCache(services, true);
        }, this);

        req.addListener("fail", e => {
          const {
            error
          } = e.getTarget().getResponse();
          console.error("getServices failed", error);
          const allServices = qxapp.dev.fake.Data.getFakeServices().concat(qxapp.utils.Services.getBuiltInServices());
          const filteredServices = qxapp.utils.Services.filterOutUnavailableGroups(allServices);
          const services = qxapp.utils.Services.convertArrayToObject(filteredServices);
          this.__servicesToCache(services, false);
        }, this);
        req.send();
        return null;
      }
      return this.__servicesCached;
    },

    __servicesToCache: function(services, fromServer) {
      this.__servicesCached = {};
      this.__addCategoryToServices(services);
      this.__servicesCached = Object.assign(this.__servicesCached, services);
      const data = {
        services: services,
        fromServer: fromServer
      };
      this.fireDataEvent("servicesRegistered", data);
      this.__reloadingServices = false;
    },

    __addCategoryToServices: function(services) {
      const cats = {
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
      for (const serviceKey in services) {
        if (Object.prototype.hasOwnProperty.call(services, serviceKey)) {
          let service = services[serviceKey];
          if (serviceKey in cats) {
            for (const version in service) {
              let serv = service[version];
              if (Object.prototype.hasOwnProperty.call(service, version)) {
                serv["category"] = cats[serviceKey]["category"];
              } else {
                serv["category"] = "Unknown";
              }
            }
          } else {
            for (const version in service) {
              service[version]["category"] = "Unknown";
            }
          }
        }
      }
    },

    stopInteractiveService(nodeId) {
      const url = "/running_interactive_services";
      const query = "/"+encodeURIComponent(nodeId);
      const request = new qxapp.io.request.ApiRequest(url+query, "DELETE");
      request.send();
    }
  }
});

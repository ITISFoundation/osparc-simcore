/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Collection of methods for studies
 *
 * @ignore(fetch)
 */

qx.Class.define("osparc.utils.Study", {
  type: "static",

  statics: {
    extractServices: function(workbench) {
      const services = [];
      Object.values(workbench).forEach(srv => {
        services.push({
          key: srv.key,
          version: srv.version
        });
      });
      return services;
    },

    getUnaccessibleServices: async function(workbench) {
      return new Promise(resolve => {
        const store = osparc.store.Store.getInstance();
        store.getServicesOnly(false)
          .then(allServices => {
            const unaccessibleServices = [];
            const services = new Set(this.extractServices(workbench));
            services.forEach(srv => {
              if (srv.key in allServices && srv.version in allServices[srv.key]) {
                return;
              }
              const idx = unaccessibleServices.findIndex(unSrv => unSrv.key === srv.key && unSrv.version === srv.version);
              if (idx === -1) {
                unaccessibleServices.push(srv);
              }
            });
            resolve(unaccessibleServices);
          });
      });
    },

    isWorkbenchUpdatable: async function(workbench) {
      return new Promise(resolve => {
        const store = osparc.store.Store.getInstance();
        store.getServicesOnly(false)
          .then(allServices => {
            const services = new Set(this.extractServices(workbench));
            const filtered = [];
            services.forEach(srv => {
              const idx = filtered.findIndex(flt => flt.key === srv.key && flt.version === srv.version);
              if (idx === -1) {
                filtered.push(srv);
              }
            });
            const updatable = filtered.some(srv => {
              const latestCompatibleMetadata = osparc.utils.Services.getLatestCompatible(allServices, srv["key"], srv["version"]);
              return latestCompatibleMetadata && srv["version"] !== latestCompatibleMetadata["version"];
            });
            resolve(updatable);
          });
      });
    },

    isWorkbenchDeprecated: function(workbench) {
      const services = new Set(this.extractServices(workbench));
      const filtered = [];
      services.forEach(srv => {
        const idx = filtered.findIndex(flt => flt.key === srv.key && flt.version === srv.version);
        if (idx === -1) {
          filtered.push(srv);
        }
      });
      const deprecated = filtered.some(srv => {
        const srvMetadata = osparc.utils.Services.getMetaData(srv["key"], srv["version"]);
        if (srvMetadata) {
          return osparc.utils.Services.isDeprecated(srvMetadata);
        }
        return false;
      });
      return deprecated;
    },

    getInaccessibleServicesMsg: function(inaccessibleServices) {
      let msg = qx.locale.Manager.tr("Service(s) not accessible:<br>");
      inaccessibleServices.forEach(unaccessibleService => {
        msg += `- ${unaccessibleService.label}:${unaccessibleService.version}<br>`;
      });
      return msg;
    },

    createStudyFromService: function(key, version) {
      return new Promise((resolve, reject) => {
        const store = osparc.store.Store.getInstance();
        store.getServicesOnly()
          .then(services => {
            if (key in services) {
              const service = version ? osparc.utils.Services.getFromObject(services, key, version) : osparc.utils.Services.getLatest(services, key);
              const newUuid = osparc.utils.Utils.uuidv4();
              const minStudyData = osparc.data.model.Study.createMyNewStudyObject();
              minStudyData["name"] = service["name"];
              if (service["thumbnail"]) {
                minStudyData["thumbnail"] = service["thumbnail"];
              }
              minStudyData["workbench"][newUuid] = {
                "key": service["key"],
                "version": service["version"],
                "label": service["name"]
              };
              if (!("ui" in minStudyData)) {
                minStudyData["ui"] = {};
              }
              if (!("workbench" in minStudyData["ui"])) {
                minStudyData["ui"]["workbench"] = {};
              }
              minStudyData["ui"]["workbench"][newUuid] = {
                "position": {
                  "x": 250,
                  "y": 100
                }
              };
              store.getInaccessibleServices(minStudyData)
                .then(inaccessibleServices => {
                  if (inaccessibleServices.length) {
                    const msg = this.getInaccessibleServicesMsg(inaccessibleServices);
                    reject({
                      message: msg
                    });
                    return;
                  }
                  const params = {
                    data: minStudyData
                  };
                  osparc.data.Resources.fetch("studies", "postNewStudy", params)
                    .then(studyData => resolve(studyData["uuid"]))
                    .catch(err => reject(err));
                });
            }
          })
          .catch(err => {
            osparc.component.message.FlashMessenger.getInstance().logAs(err.message, "ERROR");
            console.error(err);
          });
      });
    },

    createStudyAndWait: function(params, interval = 1000) {
      return new Promise((resolve, reject) => {
        osparc.data.Resources.fetch("studies", "postNewStudy", params)
          .then(resp => {
            if ("status_href" in resp) {
              resolve(this.pollTaskState(resp), interval);
            } else {
              reject("Status missing");
            }
          })
          .catch(err => reject(err));
      });
    },

    pollTaskState: function(task, interval) {
      return new Promise((resolve, reject) => {
        fetch(task["status_href"])
          .then(resp => {
            if (resp.status === 200) {
              return resp.json();
            }
            reject("Status call failed");
            return null;
          })
          .then(data => {
            if (data === null || !("data" in data)) {
              reject("Data missing in Status response");
            }
            const response = data["data"];
            if (response["done"] === true) {
              fetch(task["result_href"])
                .then(res => res.json())
                .then(result => {
                  if (result && "data" in result && "result" in result["data"]) {
                    resolve(result["data"]["result"]);
                  } else {
                    reject("Missing result");
                  }
                })
                .catch(err => reject(err));
            } else {
              setTimeout(this.pollTaskState(task["status_href"]), interval);
            }
          })
          .catch(err => reject(err));
      });
    },

    createStudyFromTemplate: function(templateData) {
      return new Promise((resolve, reject) => {
        const store = osparc.store.Store.getInstance();
        store.getInaccessibleServices(templateData)
          .then(inaccessibleServices => {
            if (inaccessibleServices.length) {
              const msg = this.getInaccessibleServicesMsg(inaccessibleServices);
              reject({
                message: msg
              });
              return;
            }
            const minStudyData = osparc.data.model.Study.createMyNewStudyObject();
            minStudyData["name"] = templateData["name"];
            minStudyData["description"] = templateData["description"];
            minStudyData["thumbnail"] = templateData["thumbnail"];
            const params = {
              url: {
                templateId: templateData["uuid"]
              },
              data: minStudyData
            };
            osparc.data.Resources.fetch("studies", "postFromStudy", params)
              .then(studyData => resolve(studyData["uuid"]))
              .catch(err => reject(err));
          });
      });
    },

    mustache: {
      mustacheRegEx: function() {
        return /{{([^{}]*)}}/g;
      },

      mustache2Var: function(mustached) {
        return mustached.replace("{{", "").replace("}}", "");
      },

      getVariables: function(obj) {
        const variables = new Set();
        const secondaryStudyDataStr = JSON.stringify(obj);
        const mustaches = secondaryStudyDataStr.match(this.self().mustache.mustacheRegEx()) || [];
        mustaches.forEach(mustache => {
          const variable = this.self().mustache.mustache2Var(mustache);
          variables.add(variable);
        });
        return Array.from(variables);
      }
    }
  }
});

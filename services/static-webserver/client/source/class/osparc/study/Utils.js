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
 */

qx.Class.define("osparc.study.Utils", {
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

    getInaccessibleServices: function(workbench) {
      const allServices = osparc.store.Services.servicesCached;
      const unaccessibleServices = [];
      const wbServices = new Set(this.extractServices(workbench));
      wbServices.forEach(srv => {
        if (srv.key in allServices && srv.version in allServices[srv.key]) {
          return;
        }
        const idx = unaccessibleServices.findIndex(unSrv => unSrv.key === srv.key && unSrv.version === srv.version);
        if (idx === -1) {
          unaccessibleServices.push(srv);
        }
      });
      return unaccessibleServices;
    },

    getInaccessibleServicesMsg: function(inaccessibleServices, workbench) {
      let msg = qx.locale.Manager.tr("Service(s) not accessible:<br>");
      Object.values(workbench).forEach(node => {
        const inaccessibleService = inaccessibleServices.find(srv => srv.key === node.key && srv.version === node.version);
        if (inaccessibleService) {
          const n = inaccessibleService.key.lastIndexOf("/");
          const friendlyKey = inaccessibleService.key.substring(n + 1);
          msg += `- ${node.label} (${friendlyKey}:${inaccessibleService.version})<br>`;
        }
      });
      return msg;
    },

    isWorkbenchUpdatable: function(workbench) {
      const services = new Set(this.extractServices(workbench));
      const isUpdatable = Array.from(services).some(srv => osparc.service.Utils.isUpdatable(srv));
      return isUpdatable;
    },

    isWorkbenchRetired: function(workbench) {
      const allServices = osparc.store.Services.servicesCached;
      const services = new Set(this.extractServices(workbench));
      const isRetired = Array.from(services).some(srv => {
        if (srv.key in allServices && srv.version in allServices[srv.key]) {
          const serviceMD = allServices[srv.key][srv.version];
          if (serviceMD["retired"]) {
            const retirementDate = new Date(serviceMD["retired"]);
            const currentDate = new Date();
            return retirementDate < currentDate;
          }
          return false;
        }
        return false;
      });
      return isRetired;
    },

    isWorkbenchDeprecated: function(workbench) {
      const allServices = osparc.store.Services.servicesCached;
      const services = new Set(this.extractServices(workbench));
      const isRetired = Array.from(services).some(srv => {
        if (srv.key in allServices && srv.version in allServices[srv.key]) {
          const serviceMD = allServices[srv.key][srv.version];
          if ("retired" in serviceMD && serviceMD["retired"]) {
            const retirementDate = new Date(serviceMD["retired"]);
            const currentDate = new Date();
            return retirementDate > currentDate;
          }
          return false;
        }
        return false;
      });
      return isRetired;
    },

    createStudyFromService: function(key, version, existingStudies, newStudyLabel, contextProps = {}) {
      return new Promise((resolve, reject) => {
        osparc.store.Services.getService(key, version)
          .then(metadata => {
            const newUuid = osparc.utils.Utils.uuidV4();
            // context props, otherwise Study will be created in the root folder of my personal workspace
            const minStudyData = Object.assign(osparc.data.model.Study.createMinStudyObject(), contextProps);
            if (newStudyLabel === undefined) {
              newStudyLabel = metadata["name"];
            }
            if (existingStudies) {
              const existingNames = existingStudies.map(study => study["name"]);
              const title = osparc.utils.Utils.getUniqueName(newStudyLabel, existingNames);
              minStudyData["name"] = title;
            } else {
              minStudyData["name"] = newStudyLabel;
            }
            if (metadata["thumbnail"]) {
              minStudyData["thumbnail"] = metadata["thumbnail"];
            }
            minStudyData["workbench"][newUuid] = {
              "key": metadata["key"],
              "version": metadata["version"],
              "label": metadata["name"]
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
            const inaccessibleServices = this.getInaccessibleServices(minStudyData["workbench"])
            if (inaccessibleServices.length) {
              const msg = this.getInaccessibleServicesMsg(inaccessibleServices, minStudyData["workbench"]);
              reject({
                message: msg
              });
              return;
            }
            const params = {
              data: minStudyData
            };
            osparc.study.Utils.createStudyAndPoll(params)
              .then(studyData => resolve(studyData["uuid"]))
              .catch(err => reject(err));
          })
          .catch(err => {
            osparc.FlashMessenger.getInstance().logAs(err.message, "ERROR");
            console.error(err);
          });
      });
    },

    createStudyAndPoll: function(params) {
      return new Promise((resolve, reject) => {
        const options = {
          pollTask: true
        };
        const fetchPromise = osparc.data.Resources.fetch("studies", "postNewStudy", params, options);
        const pollTasks = osparc.data.PollTasks.getInstance();
        const interval = 1000;
        pollTasks.createPollingTask(fetchPromise, interval)
          .then(task => {
            task.addListener("resultReceived", e => {
              const resultData = e.getData();
              resolve(resultData);
            });
            task.addListener("pollingError", e => {
              const err = e.getData();
              reject(err);
            });
          })
          .catch(err => reject(err));
      });
    },

    createStudyFromTemplate: function(templateData, loadingPage, contextProps = {}) {
      return new Promise((resolve, reject) => {
        const inaccessibleServices = this.getInaccessibleServices(templateData["workbench"]);
        if (inaccessibleServices.length) {
          const msg = this.getInaccessibleServicesMsg(inaccessibleServices, templateData["workbench"]);
          reject({
            message: msg
          });
          return;
        }
        // context props, otherwise Study will be created in the root folder of my personal workspace
        const minStudyData = Object.assign(osparc.data.model.Study.createMinStudyObject(), contextProps);
        minStudyData["name"] = templateData["name"];
        minStudyData["description"] = templateData["description"];
        minStudyData["thumbnail"] = templateData["thumbnail"];
        const params = {
          url: {
            templateId: templateData["uuid"]
          },
          data: minStudyData
        };
        const options = {
          pollTask: true
        };
        const fetchPromise = osparc.data.Resources.fetch("studies", "postNewStudyFromTemplate", params, options);
        const pollTasks = osparc.data.PollTasks.getInstance();
        const interval = 1000;
        pollTasks.createPollingTask(fetchPromise, interval)
          .then(task => {
            const title = qx.locale.Manager.tr("CREATING ") + osparc.product.Utils.getStudyAlias({allUpperCase: true}) + " ...";
            const progressSequence = new osparc.widget.ProgressSequence(title).set({
              minHeight: 180 // four tasks
            });
            progressSequence.addOverallProgressBar();
            loadingPage.clearMessages();
            loadingPage.addWidgetToMessages(progressSequence);
            task.addListener("updateReceived", e => {
              const updateData = e.getData();
              if ("task_progress" in updateData && loadingPage) {
                const progress = updateData["task_progress"];
                const message = progress["message"];
                const percent = progress["percent"] ? parseFloat(progress["percent"].toFixed(3)) : progress["percent"];
                progressSequence.setOverallProgress(percent);
                const existingTask = progressSequence.getTask(message);
                if (existingTask) {
                  // update task
                  osparc.widget.ProgressSequence.updateTaskProgress(existingTask, {
                    value: percent,
                    progressLabel: parseFloat((percent*100).toFixed(2)) + "%"
                  });
                } else {
                  // new task
                  // all the previous steps to 100%
                  progressSequence.getTasks().forEach(tsk => osparc.widget.ProgressSequence.updateTaskProgress(tsk, {
                    value: 1,
                    progressLabel: "100%"
                  }));
                  // and move to the next new task
                  const subTask = progressSequence.addNewTask(message);
                  osparc.widget.ProgressSequence.updateTaskProgress(subTask, {
                    value: percent,
                    progressLabel: "0%"
                  });
                }
              }
            }, this);
            task.addListener("resultReceived", e => {
              const studyData = e.getData();
              resolve(studyData);
            }, this);
            task.addListener("pollingError", e => {
              const err = e.getData();
              reject(err);
            }, this);
          })
          .catch(err => reject(err));
      });
    },

    __getBlockedState: function(studyData) {
      if (studyData["workbench"]) {
        const unaccessibleServices = osparc.study.Utils.getInaccessibleServices(studyData["workbench"])
        if (unaccessibleServices.length) {
          return "UNKNOWN_SERVICES";
        }
      }
      if (studyData["state"] && studyData["state"]["locked"] && studyData["state"]["locked"]["value"]) {
        return "IN_USE";
      }
      return false;
    },

    canBeOpened: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return [false].includes(blocked);
    },

    canShowBillingOptions: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return [false].includes(blocked);
    },

    canShowServiceUpdates: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return [false].includes(blocked);
    },

    canShowServiceBootOptions: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return [false].includes(blocked);
    },

    canShowStudyData: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return [false].includes(blocked);
    },

    canShowPreview: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return [false].includes(blocked);
    },

    canBeDeleted: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return ["UNKNOWN_SERVICES", false].includes(blocked);
    },

    canBeDuplicated: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return [false].includes(blocked);
    },

    canBeExported: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return ["UNKNOWN_SERVICES", false].includes(blocked);
    },

    canMoveTo: function(studyData) {
      const blocked = this.__getBlockedState(studyData);
      return ["UNKNOWN_SERVICES", false].includes(blocked);
    },
  }
});

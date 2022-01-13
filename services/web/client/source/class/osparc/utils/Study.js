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

qx.Class.define("osparc.utils.Study", {
  type: "static",

  statics: {
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
        store.getServicesDAGs()
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
                  osparc.data.Resources.fetch("studies", "post", params)
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
            osparc.data.Resources.fetch("studies", "postFromTemplate", params)
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

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
 * Collection of static methods for handling parametrized studies
 */

qx.Class.define("osparc.data.StudyParametrizer", {
  type: "static",

  statics: {
    /**
     * Calculate the steps for the given parameter specs.
     * In: {low: 0, high: 3, nSteps: 4}
     * Out:[0, 1, 2, 3]
     * @param args {Array} Array of arrays
     */
    calculateSteps: function(params) {
      const arrs = [];
      params.forEach(param => {
        const arr = [];
        const step = param.nSteps > 1 ? ((param.high - param.low) / (param.nSteps-1)) : 0;
        for (let i=0; i<param.nSteps; i++) {
          arr.push(param.low + step*i);
        }
        arrs.push(arr);
      });
      return arrs;
    },

    /**
     * https://stackoverflow.com/questions/15298912/javascript-generating-combinations-from-n-arrays-with-m-elements
     * Calculate all cartesian combinations for the given array of arrays.
     * In: [[1, 2], [3, 4]]
     * Out: [[1, 3], [1, 4], [2, 3], [2, 4]]
     * @param args {Array} Array of arrays
     */
    calculateCombinations: function(args) {
      const r = [];
      if (args.length) {
        const max = args.length-1;
        const helper = (arr, i) => {
          for (let j=0, l=args[i].length; j<l; j++) {
            const a = arr.slice(0);
            a.push(args[i][j]);
            if (i === max) {
              r.push(a);
            } else {
              helper(a, i+1);
            }
          }
        };
        helper([], 0);
      }
      return r;
    },

    getActiveParameters: function(studyData, parameters) {
      const activeParams = [...parameters];

      const variableIds = osparc.utils.Utils.mustache.getVariables(studyData);
      for (let i=activeParams.length-1; i>=0; i--) {
        if (!variableIds.includes(activeParams[i].id)) {
          activeParams.splice(i, 1);
        }
      }

      return activeParams;
    },

    recreateIterations: function(primaryStudyData, parameters, combinations) {
      return new Promise((resolve, reject) => {
        const store = osparc.store.Store.getInstance();
        store.getGroupsMe()
          .then(groupMe => {
            const templatePrimaryStudyData = osparc.data.model.Study.deepCloneStudyObject(primaryStudyData);
            templatePrimaryStudyData["accessRights"][groupMe.gid] = osparc.component.export.Permissions.getOwnerAccessRight();
            const params = {
              url: {
                "study_id": this.__studyId
              },
              data: templatePrimaryStudyData
            };
            osparc.data.Resources.fetch("templates", "postToTemplate", params)
              .then(temporaryTemplate => {
                const promisesCreateSecs = [];
                for (let i=0; i<combinations.length; i++) {
                  const paramsSec = {
                    url: {
                      templateId: temporaryTemplate.uuid
                    },
                    data: {
                      "name": temporaryTemplate["name"] + " (it-" + (i+1) + ")"
                    }
                  };
                  promisesCreateSecs.push(osparc.data.Resources.fetch("studies", "postFromTemplate", paramsSec));
                }
                Promise.all(promisesCreateSecs)
                  .then(secondaryStudiesData => {
                    if (secondaryStudiesData.length !== combinations.length) {
                      reject("Number of combinations is not the same as the secondary studies created");
                    }
                    const promisesUpdateSecs = [];
                    for (let i=0; i<combinations.length; i++) {
                      const combination = combinations[i];
                      let secondaryStudyData = secondaryStudiesData[i];
                      let secondaryStudyDataStr = JSON.stringify(secondaryStudyData);
                      const parameterValues = [];
                      for (let j=0; j<combination.length; j++) {
                        const varValue = combination[j];
                        const parameterId = parameters[j].id;
                        const mustachedStr = "\"{{" + parameterId + "}}\"";
                        secondaryStudyDataStr = secondaryStudyDataStr.replace(mustachedStr, varValue);
                        const parameterValue = {};
                        parameterValue[parameterId] = varValue;
                        parameterValues.push(parameterValue);
                      }
                      secondaryStudyData = JSON.parse(secondaryStudyDataStr);
                      secondaryStudyData["dev"] = {
                        "sweeper": {
                          "primaryStudyId": primaryStudyData.uuid,
                          "parameterValues": parameterValues
                        }
                      };
                      const paramsUpdateSec = {
                        url: {
                          "projectId": secondaryStudyData["uuid"]
                        },
                        data: secondaryStudyData
                      };
                      promisesUpdateSecs.push(osparc.data.Resources.fetch("studies", "put", paramsUpdateSec));
                    }
                    Promise.all(promisesUpdateSecs)
                      .then(updatedSecondaryStudiesData => {
                        const paramsTemp = {
                          url: {
                            projectId: temporaryTemplate.uuid
                          }
                        };
                        osparc.data.Resources.fetch("templates", "delete", paramsTemp, temporaryTemplate.uuid)
                          .then(() => {
                            resolve(updatedSecondaryStudiesData);
                          });
                      });
                  });
              });
          });
      });
    }
  }
});

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
 * Collection of static methods for handling studies with file sweepers
 */

qx.Class.define("osparc.data.StudyFileSweeper", {
  type: "static",

  statics: {
    getFileSweepers: function(studyData) {
      const fileSweepers = [];
      for (const nodeId in studyData.workbench) {
        const node = studyData.workbench[nodeId];
        if (osparc.data.model.Node.isFileSweeper(node)) {
          const nodeCopy = osparc.utils.Utils.deepCloneObject(node);
          nodeCopy.id = nodeId;
          fileSweepers.push(nodeCopy);
        }
      }
      return fileSweepers;
    },

    calculateCombinations: function(studyData) {
      const r = [];

      const steps = [];
      const fileSweepers = this.getFileSweepers(studyData);
      fileSweepers.forEach(fileSweeper => {
        if ("outFiles" in fileSweeper.outputs) {
          const step = [];
          fileSweeper.outputs.outFiles.forEach(output => {
            const out = {};
            out.id = fileSweeper.id;
            out.value = osparc.utils.Utils.deepCloneObject(output);
            step.push(out);
          });
          steps.push(step);
        }
      });

      if (steps.length) {
        const max = steps.length-1;
        const helper = (arr, i) => {
          for (let j=0, l=steps[i].length; j<l; j++) {
            const a = arr.slice(0);
            a.push(steps[i][j]);
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

    recreateIterations: function(primaryStudyData, fileSweepers, combinations) {
      return new Promise((resolve, reject) => {
        const store = osparc.store.Store.getInstance();
        store.getGroupsMe()
          .then(groupMe => {
            const templatePrimaryStudyData = osparc.data.model.Study.deepCloneStudyObject(primaryStudyData);
            templatePrimaryStudyData["accessRights"][groupMe.gid] = osparc.component.export.StudyPermissions.getOwnerAccessRight();
            const params = {
              url: {
                "study_id": templatePrimaryStudyData.uuid
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

                      const fileSweepers2 = this.getFileSweepers(secondaryStudyData);
                      if (fileSweepers2.length !== combination.length) {
                        reject("Number of file sweepers is not the same in the secondary studies created");
                      }

                      const parameterValues = this.__replaceFileSweepers(secondaryStudyData, combination);

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
    },

    __replaceFileSweepers: function(secondaryStudyData, combination) {
      let j = 0;
      const parameterValues = [];
      for (const nodeId in secondaryStudyData.workbench) {
        const node = secondaryStudyData.workbench[nodeId];
        if (osparc.data.model.Node.isFileSweeper(node)) {
          node.key = "simcore/services/frontend/file-picker";
          node.version = "1.0.0";
          node.outputs.outFile = combination[j].value;
          delete node.outputs.outFiles;

          const parameterValue = {};
          parameterValue[nodeId] = j;
          parameterValues.push(parameterValue);
          j++;
        }
      }
      let secondaryStudyDataStr = JSON.stringify(secondaryStudyData.workbench);
      const outFilesStr = "\"output\":\"outFiles\"";
      const outFileStr = "\"output\":\"outFile\"";
      console.log(secondaryStudyDataStr.indexOf(outFilesStr));
      secondaryStudyDataStr = secondaryStudyDataStr.replaceAll(outFilesStr, outFileStr);
      secondaryStudyData.workbench = JSON.parse(secondaryStudyDataStr);
      return parameterValues;
    }
  }
});

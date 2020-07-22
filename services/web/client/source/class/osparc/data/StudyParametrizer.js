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
 *   Collection of static methods for handling parametrized studies
 */

qx.Class.define("osparc.data.StudyParametrizer", {
  type: "static",

  statics: {
    recreateIterations: function(primaryStudyData) {
      const secondaryStudiesData = [];

      // OM: mustache
      const newVals = [3, 4, 5];
      newVals.forEach((newVal, idx) => {
        const delta = {};
        const firstSleeperId = Object.keys(primaryStudyData["workbench"])[0];
        delta[firstSleeperId] = {
          "inputs": {
            "in_2": newVal
          }
        };
        const secondaryStudyData = osparc.data.StudyParametrizer.createStudyParameterization(primaryStudyData, delta, idx);
        if (secondaryStudyData) {
          console.log(secondaryStudyData);
          secondaryStudiesData.push(secondaryStudyData);
        }
      });

      return secondaryStudiesData;
    },

    __applyDelta: function(secondaryStudyData, delta) {
      // apply iteration delta
      if (Object.keys(delta).length !== 1) {
        console.error("One nodeId per delta");
        return false;
      }
      const nodeId = Object.keys(delta)[0];
      if (nodeId in secondaryStudyData["workbench"]) {
        const inputs = secondaryStudyData["workbench"][nodeId]["inputs"];
        if (Object.keys(delta[nodeId]["inputs"]).length !== 1) {
          console.error("One inputId per delta");
          return false;
        }
        const inputKey = Object.keys(delta[nodeId]["inputs"])[0];
        if (inputKey in inputs) {
          inputs[inputKey] = delta[nodeId]["inputs"][inputKey];
          return true;
        }
      }
      return false;
    },

    createStudyParameterization: function(primaryStudyData, delta, idx) {
      const secondaryStudyData = osparc.data.model.Study.deepCloneStudyObject(primaryStudyData);
      if (osparc.data.StudyParametrizer.__applyDelta(secondaryStudyData, delta)) { // eslint-disable-line no-underscore-dangle
        // give new study id
        secondaryStudyData["uuid"] = osparc.utils.Utils.uuidv4();
        // give a different name
        secondaryStudyData["name"] = secondaryStudyData["name"] + " (it-" + (idx+1) + ")";
        // replace orignal uuids
        secondaryStudyData["workbench"] = osparc.data.Converters.replaceUuids(secondaryStudyData["workbench"]);
        // make them read only

        return secondaryStudyData;
      }
      return null;
    }
  }
});

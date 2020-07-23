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
     * In: {low: 0, high: 3, steps: 4}
     * Out:[0, 1, 2, 3]
     * @param args {Array} Array of arrays
     */
    calculateSteps: function(params) {
      const arrs = [];
      params.forEach(param => {
        const arr = [];
        const step = param.steps > 1 ? ((param.high - param.low) / (param.steps-1)) : 0;
        for (let i=0; i<param.steps; i++) {
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
      const max = args.length-1;
      const helper = (arr, i) => {
        for (let j=0, l=args[i].length; j<l; j++) {
          const a = arr.slice(0); // clone arr
          a.push(args[i][j]);
          if (i === max) {
            r.push(a);
          } else {
            helper(a, i+1);
          }
        }
      };
      helper([], 0);
      return r;
    },

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
        // eslint-disable-next-line no-underscore-dangle
        const secondaryStudyData = osparc.data.StudyParametrizer.__createStudyParameterization(primaryStudyData, delta, idx);
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

    __createStudyParameterization: function(primaryStudyData, delta, idx) {
      const secondaryStudyData = osparc.data.model.Study.deepCloneStudyObject(primaryStudyData);
      // eslint-disable-next-line no-underscore-dangle
      if (osparc.data.StudyParametrizer.__applyDelta(secondaryStudyData, delta)) {
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

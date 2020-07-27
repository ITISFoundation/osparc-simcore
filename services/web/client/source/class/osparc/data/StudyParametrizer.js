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

    recreateIterations: function(primaryStudyData, parameters, combinations) {
      const secondaryStudiesData = [];

      combinations.forEach((combination, idx) => {
        // eslint-disable-next-line no-underscore-dangle
        let secondaryStudyData = osparc.data.StudyParametrizer.__createSecondaryStudy(primaryStudyData, idx);
        let secondaryStudyDataStr = JSON.stringify(secondaryStudyData);
        combination.forEach((varValue, idx2) => {
          const parameter = parameters[idx2];
          // do the mustache thing
          const mustachedStr = "{{" + parameter.id + "}}";
          secondaryStudyDataStr = secondaryStudyDataStr.replace(mustachedStr, varValue);
        });
        secondaryStudyData = JSON.parse(secondaryStudyDataStr);
        secondaryStudiesData.push(secondaryStudyData);
      });

      return secondaryStudiesData;
    },

    __createSecondaryStudy: function(primaryStudyData, idx) {
      const secondaryStudyData = osparc.data.model.Study.deepCloneStudyObject(primaryStudyData);

      // give new study id
      secondaryStudyData["uuid"] = osparc.utils.Utils.uuidv4();
      // give a different name
      secondaryStudyData["name"] = secondaryStudyData["name"] + " (it-" + (idx+1) + ")";
      // replace orignal uuids
      secondaryStudyData["workbench"] = osparc.data.Converters.replaceUuids(secondaryStudyData["workbench"]);

      // set primary study Id
      secondaryStudyData["dev"] = {};
      secondaryStudyData["dev"]["sweeper"] = {};
      secondaryStudyData["dev"]["sweeper"]["primaryStudyId"] = primaryStudyData.uuid;

      return secondaryStudyData;
    }
  }
});

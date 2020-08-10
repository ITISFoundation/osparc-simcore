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
 * Class that stores Sweeper related data.
 */

qx.Class.define("osparc.data.model.Sweeper", {
  extend: qx.core.Object,

  /**
    * @param studyData {Object} Object containing the serialized Study Data
   */
  construct: function(studyData = {}) {
    this.base(arguments);

    this.__parameters = [];
    this.__parameterValues = [];
    this.__combinations = [];
    this.__secondaryStudyIds = [];
    this.__primaryStudyId = null;

    if ("dev" in studyData && "sweeper" in studyData["dev"]) {
      this.deserializeSweeper(studyData["dev"]["sweeper"]);
    }
  },

  statics: {
    isSweeperEnabled: function() {
      return new Promise((resolve, reject) => {
        osparc.utils.LibVersions.getPlatformName()
          .then(platformName => {
            if (["dev", "master"].includes(platformName)) {
              resolve(true);
            } else {
              resolve(false);
            }
          });
      });
    }
  },

  events: {
    "changeParameters": "qx.event.type.Event"
  },

  members: {
    __parameters: null,
    __parameterValues: null,
    __combinations: null,
    __secondaryStudyIds: null,
    __primaryStudyId: null,

    /* PARAMETERS */
    hasParameters: function() {
      return Boolean(Object.keys(this.__parameters).length);
    },

    getParameter: function(parameterId) {
      return this.__parameters.find(parameter => parameter.id === parameterId);
    },

    getParameters: function() {
      return this.__parameters;
    },

    parameterLabelExists: function(parameterLabel) {
      const params = this.getParameters();
      const idx = params.findIndex(param => param.label === parameterLabel);
      return (idx !== -1);
    },

    __setParameters: function(parameters) {
      this.__parameters = parameters;
      this.fireEvent("changeParameters");
    },

    addNewParameter: function(parameterLabel) {
      if (!this.parameterLabelExists(parameterLabel)) {
        const parameter = {
          id: parameterLabel,
          label: parameterLabel,
          low: 1,
          high: 2,
          nSteps: 2,
          distribution: "linear"
        };
        this.__parameters.push(parameter);

        this.fireEvent("changeParameters");

        return parameter;
      }
      return null;
    },
    /* /PARAMETERS */

    /* /PARAMETER VALUES */
    hasParameterValues: function() {
      return Boolean(this.__parameterValues.length);
    },

    getParameterValues: function() {
      return this.__parameterValues;
    },

    __setParameterValues: function(parameterValues) {
      this.__parameterValues = parameterValues;
    },
    /* /PARAMETER VALUES */

    /* COMBINATIONS */
    __hasCombinations: function() {
      return this.__combinations.length;
    },

    getCombinations: function() {
      return this.__combinations;
    },

    __setCombinations: function(combinations) {
      this.__combinations = combinations;
    },
    /* /COMBINATIONS */

    /* SECONDARY STUDIES */
    hasSecondaryStudies: function() {
      return this.__secondaryStudyIds.length;
    },

    getSecondaryStudyIds: function() {
      return this.__secondaryStudyIds;
    },

    __removeSecondaryStudy: function(secondaryStudyId) {
      return new Promise((resolve, reject) => {
        this.__deleteSecondaryStudy(secondaryStudyId)
          .then(() => {
            const idx = this.__secondaryStudyIds.findIndex(secStudyId => secStudyId === secondaryStudyId);
            if (idx > -1) {
              this.__secondaryStudyIds.splice(idx, 1);
            }
          })
          .catch(er => {
            console.error(er);
          })
          .finally(() => resolve());
      });
    },

    removeSecondaryStudies: function() {
      const deletePromises = [];
      this.getSecondaryStudyIds().forEach(secondaryStudyId => {
        deletePromises.push(this.__removeSecondaryStudy(secondaryStudyId));
      });
      return new Promise((resolve, reject) => {
        Promise.all(deletePromises)
          .then(() => {
            resolve();
          });
      });
    },

    __setSecondaryStudies: function(secondaryStudyIds) {
      secondaryStudyIds.forEach(secondaryStudyId => {
        this.__secondaryStudyIds.push(secondaryStudyId);
      });
    },

    __deleteSecondaryStudy: function(secondaryStudyId) {
      return osparc.store.Store.getInstance().deleteStudy(secondaryStudyId);
    },
    /* /SECONDARY STUDIES */

    /* PRIMARY STUDY */
    __setPrimaryStudyId: function(primaryStudyId) {
      this.__primaryStudyId = primaryStudyId;
    },

    getPrimaryStudyId: function() {
      return this.__primaryStudyId;
    },
    /* /PRIMARY STUDY */

    recreateIterations: function(primaryStudyData) {
      return new Promise((resolve, reject) => {
        // delete previous iterations
        this.removeSecondaryStudies()
          .then(() => {
            const usedParams = osparc.data.StudyParametrizer.getActiveParameters(primaryStudyData, this.__parameters);

            const steps = osparc.data.StudyParametrizer.calculateSteps(usedParams);
            if (steps.length !== usedParams.length) {
              console.error("Number of elements in the array of steps must be the same as parameters");
              reject();
            }

            const combinations = osparc.data.StudyParametrizer.calculateCombinations(steps);
            this.__setCombinations(combinations);

            osparc.data.StudyParametrizer.recreateIterations(primaryStudyData, usedParams, combinations)
              .then(secondaryStudiesData => {
                secondaryStudiesData.forEach(secondaryStudyData => {
                  this.__secondaryStudyIds.push(secondaryStudyData.uuid);
                });
                resolve(this.getSecondaryStudyIds());
              });
          });
      });
    },

    serializeSweeper: function() {
      const obj = {};

      if (this.hasParameters()) {
        obj["parameters"] = [];
        this.getParameters().forEach(parameter => {
          obj["parameters"].push(parameter);
        });
      }

      if (this.hasParameterValues()) {
        obj["parameterValues"] = [];
        this.getParameterValues().forEach(parameterValue => {
          obj["parameterValues"].push(parameterValue);
        });
      }

      if (this.__hasCombinations()) {
        obj["combinations"] = [];
        this.getCombinations().forEach(combination => {
          obj["combinations"].push(combination);
        });
      }

      if (this.hasSecondaryStudies()) {
        obj["secondaryStudyIds"] = [];
        this.getSecondaryStudyIds().forEach(secondaryStudyId => {
          obj["secondaryStudyIds"].push(secondaryStudyId);
        });
      }

      const primaryStudyId = this.getPrimaryStudyId();
      if (primaryStudyId) {
        obj["primaryStudyId"] = primaryStudyId;
      }

      return obj;
    },

    deserializeSweeper: function(sweeperData) {
      if ("parameters" in sweeperData) {
        this.__setParameters(sweeperData["parameters"]);
      }

      if ("parameterValues" in sweeperData) {
        this.__setParameterValues(sweeperData["parameterValues"]);
      }

      if ("combinations" in sweeperData) {
        this.__setCombinations(sweeperData["combinations"]);
      }

      if ("secondaryStudyIds" in sweeperData) {
        this.__setSecondaryStudies(sweeperData["secondaryStudyIds"]);
      }

      if ("primaryStudyId" in sweeperData) {
        this.__setPrimaryStudyId(sweeperData["primaryStudyId"]);
      }
    }
  }
});

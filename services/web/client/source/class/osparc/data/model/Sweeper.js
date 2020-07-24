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
    this.__combinations = [];
    this.__secondaryStudyIds = [];
    this.__primaryStudyId = null;

    this.deserializeSweeper(studyData);
  },

  events: {
    "changeParameters": "qx.event.type.Event",
    "changeSecondaryStudies": "qx.event.type.Event"
  },

  members: {
    __parameters: null,
    __combinations: null,
    __secondaryStudyIds: null,
    __primaryStudyId: null,

    /* PARAMETERS */
    hasParameters: function() {
      return Boolean(Object.keys(this.__parameters).length);
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
          steps: 2,
          distribution: "linear"
        };
        this.__parameters.push(parameter);

        this.fireEvent("changeParameters");

        return parameter;
      }
      return null;
    },
    /* /PARAMETERS */

    /* COMBINATIONS */
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

    __addSecondaryStudy: function(secondaryStudy) {
      this.__postSecondaryStudy(secondaryStudy)
        .then(studyData => {
          this.__secondaryStudyIds.push(studyData.uuid);
          this.fireEvent("changeSecondaryStudies");
        })
        .catch(er => {
          console.error(er);
        });
    },

    __removeSecondaryStudy: function(secondaryStudyId) {
      this.__deleteSecondaryStudy(secondaryStudyId)
        .then(() => {
          const idx = this.__secondaryStudyIds.findIndex(secStudyId => secStudyId === secondaryStudyId);
          if (idx > -1) {
            this.__secondaryStudyIds.splice(idx, 1);
            this.fireEvent("changeSecondaryStudies");
          }
        })
        .catch(er => {
          console.error(er);
        });
    },

    __setSecondaryStudies: function(secondaryStudyIds) {
      secondaryStudyIds.forEach(secondaryStudyId => {
        this.__secondaryStudyIds.push(secondaryStudyId);
        this.fireEvent("changeSecondaryStudies");
      });
    },

    __postSecondaryStudy: function(secondaryStudy) {
      const params = {
        data: secondaryStudy
      };
      return osparc.data.Resources.fetch("studies", "post", params);
    },

    __deleteSecondaryStudy: function(secondaryStudyId) {
      const params = {
        url: {
          projectId: secondaryStudyId
        }
      };
      return osparc.data.Resources.fetch("studies", "delete", params, secondaryStudyId);
    },
    /* /SECONDARY STUDIES */

    /* PRIMARY STUDY */
    setPrimaryStudyId: function(primaryStudyId) {
      this.__primaryStudyId = primaryStudyId;
    },

    getPrimaryStudyId: function() {
      return this.__primaryStudyId;
    },
    /* /PRIMARY STUDY */

    recreateIterations: function(primaryStudyData) {
      this.getSecondaryStudyIds().forEach(secondaryStudyId => {
        this.__removeSecondaryStudy(secondaryStudyId);
      });

      const steps = osparc.data.StudyParametrizer.calculateSteps(this.__parameters);

      if (steps.length !== this.__parameters.length) {
        console.error("Number of elements in the array of steps must be the same as parameters");
        return null;
      }
      const combinations = osparc.data.StudyParametrizer.calculateCombinations(steps);
      this.__setCombinations(combinations);

      const secondaryStudiesData = osparc.data.StudyParametrizer.recreateIterations(primaryStudyData, this.__parameters, this.__combinations);
      secondaryStudiesData.forEach(secondaryStudyData => {
        this.__addSecondaryStudy(secondaryStudyData);
      });

      return secondaryStudiesData;
    },

    serializeSweeper: function() {
      const obj = {};

      if (this.hasParameters()) {
        obj["parameters"] = [];
        this.getParameters().forEach(parameter => {
          obj["parameters"].push(parameter);
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

    deserializeSweeper: function(studyData) {
      if ("parameters" in studyData) {
        this.__setParameters(studyData["parameters"]);
      }

      if ("secondaryStudyIds" in studyData) {
        this.__setSecondaryStudies(studyData["secondaryStudyIds"]);
      }

      if ("primaryStudyId" in studyData) {
        this.setPrimaryStudyId(studyData["primaryStudyId"]);
      }
    }
  }
});

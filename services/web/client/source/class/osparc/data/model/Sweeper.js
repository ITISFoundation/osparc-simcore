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
  construct: function(studyData) {
    this.base(arguments);

    this.__parameters = [];
    this.__steps = [];
    this.__combinations = [];
    this.__secondaryStudies = [];
    this.__primaryStudyId = null;

    this.deserializeSweeper(studyData);
  },

  events: {
    "changeParameters": "qx.event.type.Data",
    "changeSecondaryStudies": "qx.event.type.Data"
  },

  members: {
    __parameters: null,
    __steps: null,
    __combinations: null,
    __secondaryStudies: null,
    __primaryStudyId: null,

    /* PARAMETERS */
    getParameters: function() {
      return this.__parameters;
    },

    parameterLabelExists: function(parameterLabel) {
      const params = this.getParameters();
      const idx = params.findIndex(param => param.label === parameterLabel);
      return (idx !== -1);
    },

    addParameter: function(parameterLabel) {
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

        this.fireDataEvent("changeParameters", this.__parameters);

        return parameter;
      }
      return null;
    },
    /* /PARAMETERS */

    /* STEPS */
    setSteps: function(steps) {
      if (steps.length !== this.__parameters.length) {
        console.error("Number of elements in the array of steps must be the same as parameters");
        return;
      }
      this.__steps = steps;

      const combinations = osparc.data.StudyParametrizer.calculateCombinations(steps);
      this.__setCombinations(combinations);
    },
    /* /STEPS */

    /* COMBINATIONS */
    getCombinations: function() {
      return this.__combinations;
    },

    __setCombinations: function(combinations) {
      this.__combinations = combinations;
    },
    /* /COMBINATIONS */

    recreateIterations: function(primaryStudyData) {
      const steps = osparc.data.StudyParametrizer.calculateSteps(this.__parameters);
      this.setSteps(steps);

      const secondaryStudiesData = osparc.data.StudyParametrizer.recreateIterations(primaryStudyData, this.__parameters, this.__combinations);
      this.__setSecondaryStudies(secondaryStudiesData);
      return secondaryStudiesData;
    },

    /* SECONDARY STUDIES */
    hasSecondaryStudies: function() {
      return Boolean(Object.keys(this.__secondaryStudies).length);
    },

    getSecondaryStudy: function(secondaryStudyId) {
      const index = this.__secondaryStudies.findIndex(secStudy => secStudy.uuid === secondaryStudyId);
      if (index !== -1) {
        return this.__secondaryStudies[index];
      }
      return null;
    },

    getSecondaryStudies: function() {
      return this.__secondaryStudies;
    },

    __addSecondaryStudy: function(secondaryStudy) {
      this.__postSecondaryStudy(secondaryStudy)
        .then(studyData => {
          this.__secondaryStudies.push(studyData);
          this.fireDataEvent("changeSecondaryStudies", this.__secondaryStudies);
        })
        .catch(er => {
          console.error(er);
        });
    },

    __removeSecondaryStudy: function(secondaryStudy) {
      this.__deleteSecondaryStudy(secondaryStudy)
        .then(() => {
          const idx = this.__secondaryStudies.findIndex(secStudy => secStudy.uuid === secondaryStudy.uuid);
          if (idx > -1) {
            this.__secondaryStudies.splice(idx, 1);
            this.fireDataEvent("changeSecondaryStudies", this.__secondaryStudies);
          }
        })
        .catch(er => {
          console.error(er);
        });
    },

    __setSecondaryStudies: function(secondaryStudies) {
      this.__secondaryStudies.forEach(secondaryStudy => {
        this.__removeSecondaryStudy(secondaryStudy);
      });

      secondaryStudies.forEach(secondaryStudy => {
        this.__addSecondaryStudy(secondaryStudy);
      });
    },

    __postSecondaryStudy: function(secondaryStudy) {
      const params = {
        data: secondaryStudy
      };
      return osparc.data.Resources.fetch("studies", "post", params);
    },

    __deleteSecondaryStudy: function(secondaryStudy) {
      const params = {
        url: {
          projectId: secondaryStudy.uuid
        }
      };
      return osparc.data.Resources.fetch("studies", "delete", params, secondaryStudy.uuid);
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

    serializeSweeper: function() {
      const obj = {};

      if (this.hasSecondaryStudies()) {
        obj["secondaryStudyIds"] = [];
        this.getSecondaryStudies().forEach(secondaryStudy => {
          obj["secondaryStudyIds"].push(secondaryStudy);
        });
      }

      const primaryStudyId = this.getPrimaryStudyId();
      if (primaryStudyId) {
        obj["primaryStudyId"] = primaryStudyId;
      }

      return obj;
    },

    deserializeSweeper: function(studyData) {
      if ("secondaryStudyIds" in studyData) {
        this.__setSecondaryStudies(studyData["secondaryStudyIds"]);
      }

      if ("primaryStudyId" in studyData) {
        this.setPrimaryStudyId(studyData["primaryStudyId"]);
      }
    }
  }
});

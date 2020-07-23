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
   * @param parametersData {Object} Object containing the parameters raw data
   */
  construct: function(parametersData) {
    this.base(arguments);

    console.log(parametersData);

    this.__parameters = [];
    this.__secondaryStudies = [];
  },

  events: {
    "changeParameters": "qx.event.type.Data",
    "changeSecondaryStudies": "qx.event.type.Data"
  },

  members: {
    __parameters: null,
    __secondaryStudies: null,

    /* PARAMETERS */
    addParameter: function(parameterLabel) {
      if (!this.parameterLabelExists(parameterLabel)) {
        const nParams = this.__parameters.length;
        const newId = nParams ? this.__parameters[nParams-1].id + 1 : 0;
        const parameter = {
          id: newId,
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

    getParameter: function(parameterId) {
      const params = this.getParameters();
      const idx = params.findIndex(param => param.id === parameterId);
      return (idx === -1) ? null : params[idx];
    },

    getParameters: function() {
      return this.__parameters;
    },

    parameterLabelExists: function(parameterLabel) {
      const params = this.getParameters();
      const idx = params.findIndex(param => param.label === parameterLabel);
      return (idx !== -1);
    },
    /* /PARAMETERS */

    /* SECONDARY STUDIES */
    addSecondaryStudy: function(secondaryStudy) {
      const index = this.__secondaryStudies.findIndex(secStudy => secStudy.uuid === secondaryStudy.uuid);
      if (index === -1) {
        this.__secondaryStudies.push(secondaryStudy);
      } else {
        this.__secondaryStudies[index] = secondaryStudy;
      }
    },

    setSecondaryStudies: function(secondaryStudies) {
      // delete old secondary studies from backend?
      this.__secondaryStudies = [];

      secondaryStudies.forEach(secondaryStudy => {
        this.addSecondaryStudy(secondaryStudy);
      });
    },

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
    }
    /* /SECONDARY STUDIES */
  }
});

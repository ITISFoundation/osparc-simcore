/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Collection of methods for studies
 */

qx.Class.define("osparc.utils.Resources", {
  type: "static",

  statics: {
    isStudy: function(studyData) {
      return ((studyData["resourceType"] === "study") && ("uuid" in studyData));
    },

    isTemplate: function(templateData) {
      return ((templateData["resourceType"] === "template") && ("uuid" in templateData));
    },

    isTutorial: function(tutorialData) {
      return ((tutorialData["resourceType"] === "tutorial") && ("uuid" in tutorialData));
    },

    isHypertool: function(hypertoolData) {
      return ((hypertoolData["resourceType"] === "hypertool") && ("uuid" in hypertoolData));
    },

    isFunction: function(functionData) {
      return ((functionData["resourceType"] === "function") && ("uuid" in functionData));
    },

    isService: function(serviceData) {
      return ((serviceData["resourceType"] === "service") && ("key" in serviceData) && ("version" in serviceData));
    },
  }
});

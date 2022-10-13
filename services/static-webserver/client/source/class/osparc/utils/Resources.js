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
      return (studyData["resourceType"] === "study");
    },

    isTemplate: function(studyData) {
      return (studyData["resourceType"] === "template");
    },

    isService: function(studyData) {
      return (studyData["resourceType"] === "service");
    }
  }
});

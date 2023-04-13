/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.product.panddy.osparc.Sequences", {
  type: "static",

  statics: {
    getSequences: function() {
      return [{
        id: "dashboard",
        name: "Dashboard",
        description: "Inotrduction to Dashboard tabs",
        steps: this.__getDashboardSteps()
      }];
    },

    __getDashboardSteps: function() {
      return [{
        target: "studiesTabBtn",
        action: "execute",
        title: "Studies",
        message: "These are your Studies."
      }, {
        target: "templatesTabBtn",
        action: "execute",
        title: "Templates",
        message: "These are the Templates you have access to. If you click on any of the cards listed below, we will create a copy of it so that you can edit it."
      }, {
        target: "servicesTabBtn",
        action: "execute",
        title: "Services",
        message: "These are the Services you have access to. Some are computational and others are dynamic. The Computational ones can be run for number crunching and the dynamic ones require user interaction."
      }, {
        target: "dataTabBtn",
        action: "execute",
        title: "Data",
        message: "This is the section where you can access all the data you produced or you have access to."
      }];
    }
  }
});

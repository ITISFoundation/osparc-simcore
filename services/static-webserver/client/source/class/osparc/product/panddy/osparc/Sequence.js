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

qx.Class.define("osparc.product.panddy.osparc.Sequence", {
  type: "static",

  statics: {
    getSteps: function() {
      return [{
        target: "studiesTabBtn",
        message: "These are your Studies.",
        action: "execute"
      }, {
        target: "templatesTabBtn",
        message: "These are the Templates you have access to. If you click on any a card, we will create a copy of it so that you can edit it.",
        action: "execute"
      }, {
        target: "servicesTabBtn",
        message: "These are the Services you have access to. Some are computational and others are dynamic. The Computational ones can be run for number crunching and the dynamic ones require user interaction.",
        action: "execute"
      }, {
        target: "dataTabBtn",
        message: "These is the section where you can access all the data you produced or you have access to.",
        action: "execute"
      }];
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.component.tutorial.Utils", {
  type: "static",

  statics: {
    TUTORIALS: {
      "tis": {
        localStorageStr: "tiDontShowQuickStart",
        tutorial: osparc.component.tutorial.ti.Slides
      },
      "s4llite": {
        localStorageStr: "s4lliteDontShowQuickStart",
        tutorial: osparc.component.tutorial.s4llite.Slides
      }
    },

    createLabel: function(text) {
      const label = new qx.ui.basic.Label().set({
        rich: true,
        wrap: true,
        font: "text-14"
      });
      if (text) {
        label.setValue(text);
      }
      return label;
    }
  }
});

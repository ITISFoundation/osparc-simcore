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
        tutorial: () => new osparc.component.tutorial.ti.Slides()
      },
      "s4llite": {
        localStorageStr: "s4lliteDontShowQuickStart",
        tutorial: () => new osparc.component.tutorial.s4llite.Slides()
      }
    },

    getTutorial: function() {
      const tutorials = osparc.component.tutorial.Utils.TUTORIALS;
      const pName = osparc.utils.Utils.getProductName();
      if (Object.keys(tutorials).includes(pName)) {
        return tutorials[pName];
      }
      return null;
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
    },

    createDontShowAgain: function(localStorageStr) {
      const dontShowCB = new qx.ui.form.CheckBox(qx.locale.Manager.tr("Don't show again")).set({
        value: osparc.utils.Utils.localCache.getLocalStorageItem(localStorageStr) === "true",
        allowGrowX: true,
        alignX: "center"
      });
      dontShowCB.addListener("changeValue", e => {
        const dontShow = e.getData();
        osparc.utils.Utils.localCache.setLocalStorageItem(localStorageStr, Boolean(dontShow));
      });
      return dontShowCB;
    }
  }
});

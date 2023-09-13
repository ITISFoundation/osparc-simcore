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

qx.Class.define("osparc.product.quickStart.Utils", {
  type: "static",

  statics: {
    QUICK_START: {
      "tis": {
        localStorageStr: "tiDontShowQuickStart",
        tutorial: () => new osparc.product.quickStart.ti.Slides()
      },
      "s4llite": {
        localStorageStr: "s4lliteDontShowQuickStart",
        tutorial: () => new osparc.product.quickStart.s4llite.Slides()
      },
      "s4l": {
        localStorageStr: "s4lDontShowQuickStart",
        tutorial: () => new osparc.product.quickStart.s4l.Slides()
      }
    },

    getQuickStart: function() {
      const quickStarts = this.QUICK_START;
      const pName = osparc.product.Utils.getProductName();
      if (Object.keys(quickStarts).includes(pName)) {
        return quickStarts[pName];
      }
      return null;
    },

    createTitle: function(title) {
      const label = new qx.ui.basic.Label(title).set({
        rich: true,
        font: "text-15"
      });
      if (title) {
        label.setValue(title);
      }
      return label;
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
        value: osparc.utils.Utils.localCache.getLocalStorageItem(localStorageStr) === "true"
      });
      dontShowCB.addListener("changeValue", e => {
        const dontShow = e.getData();
        osparc.utils.Utils.localCache.setLocalStorageItem(localStorageStr, Boolean(dontShow));
      });
      return dontShowCB;
    }
  }
});

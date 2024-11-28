/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.vipStore.StoreWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "store", this.tr("Store"));


    osparc.utils.Utils.setIdToWidget(this, "storeWindow");

    const width = 1035;
    const height = 700;
    this.set({
      width,
      height
    })

    const vipStore = this.__vipStore = new osparc.vipStore.Store();
    this._setTabbedView(vipStore);
  },

  statics: {
    openWindow: function() {
      const storeWindow = new osparc.vipStore.StoreWindow();
      storeWindow.center();
      storeWindow.open();
      return storeWindow;
    }
  },

  members: {
    __vipStore: null,

    openVIPStore: function() {
      return this.__vipStore.openVIPStore();
    },
  }
});

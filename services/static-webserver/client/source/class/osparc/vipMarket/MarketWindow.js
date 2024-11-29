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

qx.Class.define("osparc.vipMarket.MarketWindow", {
  extend: osparc.ui.window.TabbedWindow,

  construct: function() {
    this.base(arguments, "store", this.tr("Market"));


    osparc.utils.Utils.setIdToWidget(this, "storeWindow");

    const width = 1035;
    const height = 700;
    this.set({
      width,
      height
    })

    const vipMarket = this.__vipMarket = new osparc.vipMarket.Market();
    this._setTabbedView(vipMarket);
  },

  statics: {
    openWindow: function() {
      const storeWindow = new osparc.vipMarket.MarketWindow();
      storeWindow.center();
      storeWindow.open();
      return storeWindow;
    }
  },

  members: {
    __vipMarket: null,

    openVipMarket: function() {
      return this.__vipMarket.openVipMarket();
    },
  }
});

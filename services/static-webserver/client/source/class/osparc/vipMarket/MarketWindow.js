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

  construct: function(nodeId, category) {
    this.base(arguments, "store", this.tr("Market"));

    osparc.utils.Utils.setIdToWidget(this, "storeWindow");

    const width = 1050;
    const height = 700;
    this.set({
      width,
      height
    });

    const vipMarket = this.__vipMarket = new osparc.vipMarket.Market(category).set({
      openBy: nodeId ? nodeId : null,
    });
    this._setTabbedView(vipMarket);
  },

  statics: {
    openWindow: function(nodeId, category) {
      if (osparc.product.Utils.showS4LStore()) {
        const storeWindow = new osparc.vipMarket.MarketWindow(nodeId, category);
        storeWindow.getVipMarket().addListener("importMessageSent", () => storeWindow.close());
        storeWindow.addListenerOnce("close", () => {
          if (storeWindow.getVipMarket()) {
            storeWindow.getVipMarket().sendCloseMessage();
          }
        });
        storeWindow.center();
        storeWindow.open();
        return storeWindow;
      }
      return null;
    }
  },

  members: {
    __vipMarket: null,

    getVipMarket: function() {
      return this.__vipMarket;
    },
  },
});

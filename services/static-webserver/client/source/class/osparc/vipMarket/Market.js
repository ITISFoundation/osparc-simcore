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

qx.Class.define("osparc.vipMarket.Market", {
  extend: osparc.ui.window.TabbedView,

  construct: function() {
    this.base(arguments);

    const miniWallet = osparc.desktop.credits.BillingCenter.createMiniWalletView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniWallet);

    this.__vipMarketPage = this.__getVipMarketPage();
  },

  members: {
    __vipMarketPage: null,

    __getVipMarketPage: function() {
      const title = this.tr("ViP Models");
      const iconSrc = "@FontAwesome5Solid/users/22";
      const vipMarketView = new osparc.vipMarket.VipMarket();
      const page = this.addTab(title, iconSrc, vipMarketView);
      return page;
    },
  }
});

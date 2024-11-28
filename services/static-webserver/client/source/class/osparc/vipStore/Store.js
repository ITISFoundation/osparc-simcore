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

qx.Class.define("osparc.vipStore.Store", {
  extend: osparc.ui.window.TabbedView,

  construct: function() {
    this.base(arguments);

    const miniWallet = osparc.desktop.credits.BillingCenter.createMiniWalletView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniWallet);

    this.__vipStorePage = this.__getVIPStorePage();
  },

  members: {
    __vipStorePage: null,

    __getVIPStorePage: function() {
      const title = this.tr("VIP Models");
      const iconSrc = "@FontAwesome5Solid/users/22";
      const vipStoreView = new osparc.vipStore.VIPStore();
      const page = this.addTab(title, iconSrc, vipStoreView);
      return page;
    },
  }
});

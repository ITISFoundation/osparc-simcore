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

    [{
      category: "humanWhole",
      label: "Humans",
      url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanWholeBody",
    }, {
      category: "humanRegion",
      label: "Humans (Region)",
      url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanBodyRegion",
    }, {
      category: "animalWhole",
      label: "Animals",
      url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnimalWholeBody",
    }, {
      category: "compPhantom",
      label: "Phantoms",
      url: "https://speag.swiss/PD_DirectDownload/getDownloadableItems/ComputationalPhantom",
    }].forEach(marketInfo => {
      this.__buildViPMarketPage(marketInfo);
    })

    // this.__vipMarketPage = this.__getVipMarketPage();
  },

  members: {
    __vipMarketPage: null,

    __getVipMarketPage: function() {
      const title = this.tr("ViP Models");
      const iconSrc = "@FontAwesome5Solid/users/20";
      const vipMarketView = new osparc.vipMarket.VipMarket();
      const page = this.addTab(title, iconSrc, vipMarketView);
      return page;
    },

    __buildViPMarketPage: function(marketInfo) {
      const title = marketInfo["label"];
      const iconSrc = "@FontAwesome5Solid/users/20";
      const vipMarketView = new osparc.vipMarket.VipMarket();
      vipMarketView.set({
        metadataUrl: marketInfo["url"],
      });
      const page = this.addTab(title, iconSrc, vipMarketView);
      return page;
    },
  }
});

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
      icon: "@FontAwesome5Solid/users/20",
      url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanWholeBody",
    }, {
      category: "humanRegion",
      label: "Humans (Region)",
      icon: "@FontAwesome5Solid/users/20",
      url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanBodyRegion",
    }, {
      category: "animalWhole",
      label: "Animals",
      icon: "@FontAwesome5Solid/users/20",
      url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnimalWholeBody",
    }, {
      category: "compPhantom",
      label: "Phantoms",
      icon: "@FontAwesome5Solid/users/20",
      url: "https://speag.swiss/PD_DirectDownload/getDownloadableItems/ComputationalPhantom",
    }].forEach(marketInfo => {
      this.__buildViPMarketPage(marketInfo);
    });
  },

  members: {
    __buildViPMarketPage: function(marketInfo) {
      const vipMarketView = new osparc.vipMarket.VipMarket();
      vipMarketView.set({
        metadataUrl: marketInfo["url"],
      });
      const page = this.addTab(marketInfo["label"], marketInfo["icon"], vipMarketView);
      page.category = marketInfo["category"];
      return page;
    },

    openCategory: function(category) {
      const viewFound = this.getChildControl("tabs-view").getChildren().find(view => view.category === category);
      if (viewFound) {
        this._openPage(viewFound);
        return true;
      }
      return false;
    },
  }
});

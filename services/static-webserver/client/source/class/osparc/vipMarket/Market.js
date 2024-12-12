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

  construct: function(category) {
    this.base(arguments);

    const miniWallet = osparc.desktop.credits.BillingCenter.createMiniWalletView().set({
      paddingRight: 10
    });
    this.addWidgetOnTopOfTheTabs(miniWallet);

    osparc.data.Resources.getInstance().getAllPages("licensedItems")
      .then(() => {
        [{
          category: "human",
          label: "Humans",
          icon: "@FontAwesome5Solid/users/20",
          url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanWholeBody",
        }, {
          category: "human_region",
          label: "Humans (Region)",
          icon: "@FontAwesome5Solid/users/20",
          url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/HumanBodyRegion",
        }, {
          category: "animal",
          label: "Animals",
          icon: "@FontAwesome5Solid/users/20",
          url: "https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnimalWholeBody",
        }, {
          category: "phantom",
          label: "Phantoms",
          icon: "@FontAwesome5Solid/users/20",
          url: "https://speag.swiss/PD_DirectDownload/getDownloadableItems/ComputationalPhantom",
        }].forEach(marketInfo => {
          this.__buildViPMarketPage(marketInfo);
        });

        if (category) {
          this.openCategory(category);
        }
      });
  },

  properties: {
    openBy: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeOpenBy",
    },
  },

  members: {
    __buildViPMarketPage: function(marketInfo) {
      const vipMarketView = new osparc.vipMarket.VipMarket();
      vipMarketView.set({
        metadataUrl: marketInfo["url"],
      });
      this.bind("openBy", vipMarketView, "openBy");
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

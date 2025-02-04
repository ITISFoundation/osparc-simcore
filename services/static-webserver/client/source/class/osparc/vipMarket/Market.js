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

  construct: function(openCategory) {
    this.base(arguments);

    const miniWallet = osparc.desktop.credits.BillingCenter.createMiniWalletView().set({
      paddingRight: 10,
      minWidth: 150,
    });
    this.addWidgetOnTopOfTheTabs(miniWallet);

    const store = osparc.store.Store.getInstance();
    const contextWallet = store.getContextWallet();
    if (!contextWallet) {
      return;
    }

    const walletId = contextWallet.getWalletId();
    const licensedItemsStore = osparc.store.LicensedItems.getInstance();
    Promise.all([
      licensedItemsStore.getLicensedItems(),
      licensedItemsStore.getPurchasedLicensedItems(walletId),
    ])
      .then(values => {
        const licensedItems = values[0];
        const categories = {};
        licensedItems.forEach(licensedItem => {
          if (licensedItem["licensedResourceData"] && licensedItem["licensedResourceData"]["categoryId"]) {
            const category = licensedItem["licensedResourceData"]["categoryId"];
            if (!(category in categories)) {
              categories[category] = [];
            }
            categories[category].push(licensedItem);
          }
        });

        const expectedCategories = [{
          categoryId: "HumanWholeBody",
          label: "Humans",
          icon: "@FontAwesome5Solid/users/20",
        }, {
          categoryId: "HumanBodyRegion",
          label: "Humans (Region)",
          icon: "@FontAwesome5Solid/users/20",
        }, {
          categoryId: "AnimalWholeBody",
          label: "Animals",
          icon: "@FontAwesome5Solid/users/20",
        }, {
          categoryId: "ComputationalPhantom",
          label: "Phantoms",
          icon: "@FontAwesome5Solid/users/20",
        }]
        expectedCategories.forEach(expectedCategory => {
          const items = categories[expectedCategory["categoryId"]];
          this.__buildViPMarketPage(expectedCategory, items);
        });

        if (openCategory) {
          this.openCategory(openCategory);
        }
      });
  },

  events: {
    "importMessageSent": "qx.event.type.Data",
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
    __buildViPMarketPage: function(marketTabInfo, licensedItems = []) {
      const vipMarketView = new osparc.vipMarket.VipMarket(licensedItems);
      vipMarketView.set({
        category: marketTabInfo["categoryId"],
      });
      this.bind("openBy", vipMarketView, "openBy");
      vipMarketView.addListener("importMessageSent", () => this.fireEvent("importMessageSent"));
      const page = this.addTab(marketTabInfo["label"], marketTabInfo["icon"], vipMarketView);
      page.category = marketTabInfo["categoryId"];
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

    sendCloseMessage: function() {
      const store = osparc.store.Store.getInstance();
      const currentStudy = store.getCurrentStudy();
      const nodeId = this.getOpenBy();
      if (currentStudy && nodeId) {
        const msg = {
          "type": "closeMarket",
        };
        currentStudy.sendMessageToIframe(nodeId, msg);
      }
    },
  }
});

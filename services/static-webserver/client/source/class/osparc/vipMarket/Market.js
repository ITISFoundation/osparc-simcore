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
    this.addWidgetToTabs(miniWallet);

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
        const purchasedItems = values[1];
        osparc.store.LicensedItems.populateSeatsFromPurchases(licensedItems, purchasedItems);
        const categories = [];
        const purchasedCategory = {
          categoryId: "purchasedModels",
          label: this.tr("Rented"),
          icon: "osparc/market/RentedModels.svg",
          items: [],
        };
        categories.push(purchasedCategory);
        licensedItems.forEach(licensedItem => {
          if (licensedItem["seats"].length) {
            purchasedCategory["items"].push(licensedItem);
            if (!openCategory) {
              openCategory = purchasedCategory["categoryId"];
            }
          }
          if (licensedItem && licensedItem["categoryId"]) {
            const categoryId = licensedItem["categoryId"];
            let category = categories.find(cat => cat["categoryId"] === categoryId);
            if (!category) {
              category = {
                categoryId,
                label: licensedItem["categoryDisplay"] || "Category",
                icon: licensedItem["categoryIcon"] || `osparc/market/${categoryId}.svg`,
                items: [],
              };
              if (!openCategory) {
                openCategory = categoryId;
              }
              categories.push(category);
            }
            category["items"].push(licensedItem);
          }
        });

        categories.forEach(category => {
          this.__buildViPMarketPage(category, category["items"]);
        });

        if (openCategory) {
          this.__openCategory(openCategory);
        }
      });
  },

  events: {
    "importMessageSent": "qx.event.type.Event",
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
    __purchasedCategoryButton: null,
    __purchasedCategoryMarket: null,

    __buildViPMarketPage: function(marketTabInfo, licensedItems = []) {
      const vipMarketView = new osparc.vipMarket.VipMarket(licensedItems);
      vipMarketView.set({
        category: marketTabInfo["categoryId"],
      });
      this.bind("openBy", vipMarketView, "openBy");
      vipMarketView.addListener("modelPurchased", () => this.__repopulatePurchasedCategory());
      vipMarketView.addListener("importMessageSent", () => this.fireEvent("importMessageSent"));
      const page = this.addTab(marketTabInfo["label"], marketTabInfo["icon"], vipMarketView);
      page.category = marketTabInfo["categoryId"];
      if (page.category === "purchasedModels") {
        this.__purchasedCategoryMarket = vipMarketView;
        this.__purchasedCategoryButton = page.getChildControl("button");
        this.__purchasedCategoryButton.setVisibility(licensedItems.length ? "visible" : "excluded");
      }
      return page;
    },

    __repopulatePurchasedCategory: function() {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      const walletId = contextWallet.getWalletId();
      const licensedItemsStore = osparc.store.LicensedItems.getInstance();
      Promise.all([
        licensedItemsStore.getLicensedItems(),
        licensedItemsStore.getPurchasedLicensedItems(walletId),
      ])
        .then(values => {
          const licensedItems = values[0];
          const purchasedItems = values[1];
          let items = [];
          licensedItems.forEach(licensedItem => {
            if (purchasedItems.find(purchasedItem => purchasedItem["licensedItemId"] === licensedItem["licensedItemId"])) {
              items.push(licensedItem);
            }
          });
          this.__purchasedCategoryButton.setVisibility(items.length ? "visible" : "excluded");
          this.__purchasedCategoryMarket.setLicensedItems(items);
        });
    },

    __openCategory: function(category) {
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

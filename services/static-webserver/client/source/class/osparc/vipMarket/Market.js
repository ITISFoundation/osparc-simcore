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

    this.__reqOpenCategory = openCategory;
    this.__populateCategories();
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
    __reqOpenCategory: null,
    __myModelsCategoryMarket: null,
    __myModelsCategoryButton: null,

    __populateCategories: function() {
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
          osparc.data.model.LicensedItem.addSeatsFromPurchases(licensedItems, purchasedItems);
          const categories = [];
          const availableCategory = {
            categoryId: "availableModels",
            label: this.tr("My Models"),
            icon: "osparc/market/RentedModels.svg",
            items: [],
          };
          categories.push(availableCategory);
          let openCategory = null;
          Object.values(licensedItems).forEach(licensedItem => {
            if (licensedItem.getSeats().length) {
              availableCategory["items"].push(licensedItem);
              if (!this.__reqOpenCategory) {
                openCategory = availableCategory["categoryId"];
              }
            }
            if (licensedItem && licensedItem.getCategoryId()) {
              const categoryId = licensedItem.getCategoryId();
              let category = categories.find(cat => cat["categoryId"] === categoryId);
              if (!category) {
                category = {
                  categoryId,
                  label: licensedItem.getCategoryDisplay() || "Category",
                  icon: licensedItem.getCategoryIcon(),
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

          this.__addFreeItems();
        });
    },

    __addFreeItems: function() {
      const licensedItemsStore = osparc.store.LicensedItems.getInstance();
      licensedItemsStore.getLicensedItems()
        .then(async licensedItems => {
          this.__freeItems = [];
          const licensedItemsArr = Object.values(licensedItems);
          for (const licensedItem of licensedItemsArr) {
            const pricingUnits = await osparc.store.Pricing.getInstance().fetchPricingUnits(licensedItem.getPricingPlanId());
            if (pricingUnits.length === 1 && pricingUnits[0].getCost() === 0) {
              this.__freeItems.push(licensedItem);
            }
          }
          if (!this.__reqOpenCategory && this.__freeItems.length) {
            this.__openCategory("availableModels");
          }
          this.__repopulateMyModelsCategory();
        });
    },

    __buildViPMarketPage: function(marketTabInfo, licensedItems = []) {
      const vipMarketView = new osparc.vipMarket.VipMarket(licensedItems);
      vipMarketView.set({
        category: marketTabInfo["categoryId"],
      });
      this.bind("openBy", vipMarketView, "openBy");
      vipMarketView.addListener("modelPurchased", () => this.__repopulateMyModelsCategory());
      vipMarketView.addListener("importMessageSent", () => this.fireEvent("importMessageSent"));
      const page = this.addTab(marketTabInfo["label"], marketTabInfo["icon"], vipMarketView);
      page.category = marketTabInfo["categoryId"];
      if (page.category === "availableModels") {
        this.__myModelsCategoryMarket = vipMarketView;
        this.__myModelsCategoryButton = page.getChildControl("button");
        this.__myModelsCategoryButton.setVisibility(licensedItems.length ? "visible" : "excluded");
      }
      return page;
    },

    __repopulateMyModelsCategory: function() {
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
          osparc.data.model.LicensedItem.addSeatsFromPurchases(licensedItems, purchasedItems);
          let items = [];
          Object.values(licensedItems).forEach(licensedItem => {
            if (licensedItem.getSeats().length) {
              items.push(licensedItem);
            }
          });
          items = items.concat(this.__freeItems);
          this.__myModelsCategoryButton.setVisibility(items.length ? "visible" : "excluded");
          this.__myModelsCategoryMarket.setLicensedItems(items);
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

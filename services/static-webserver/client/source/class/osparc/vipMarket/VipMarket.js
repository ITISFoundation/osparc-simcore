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

qx.Class.define("osparc.vipMarket.VipMarket", {
  extend: qx.ui.splitpane.Pane,

  construct: function(licensedItems) {
    this.base(arguments, "horizontal");

    this.setOffset(5);
    this.getChildControl("splitter").set({
      width: 1,
      backgroundColor: "text",
      opacity: 0.3,
    });
    this.getChildControl("slider").set({
      width: 2,
      backgroundColor: "text",
      opacity: 1,
    });

    this.__buildLayout();

    if (licensedItems) {
      this.setLicensedItems(licensedItems);
    }
  },

  events: {
    "modelPurchased": "qx.event.type.Event",
    "importMessageSent": "qx.event.type.Event",
  },

  properties: {
    openBy: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeOpenBy",
    },

    category: {
      check: "String",
      init: null,
      nullable: true,
    },
  },

  members: {
    __anatomicalBundles: null,
    __anatomicalBundlesModel: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "left-side":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignY: "middle",
            paddingRight: 5,
          });
          this.add(control, 0); // flex: 0
          break;
        case "right-side":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignY: "middle",
            paddingLeft: 5,
          });
          this.add(control, 1); // flex: 1
          break;
        case "toolbar-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
            alignY: "middle",
          });
          this.getChildControl("left-side").add(control);
          break;
        case "sort-button":
          control = new osparc.vipMarket.SortModelsButtons().set({
            alignY: "bottom",
            maxHeight: 27,
          });
          this.getChildControl("toolbar-layout").add(control);
          break;
        case "filter-text":
          control = new osparc.filter.TextFilter("text", "vipModels").set({
            alignY: "middle",
            allowGrowY: false,
            allowGrowX: true,
            marginRight: 5,
          });
          control.getChildControl("textfield").set({
            backgroundColor: "transparent",
            allowGrowX: true,
          });
          this.addListener("appear", () => control.getChildControl("textfield").focus());
          this.getChildControl("toolbar-layout").add(control, {
            flex: 1
          });
          break;
        case "models-list":
          control = new qx.ui.form.List().set({
            decorator: "no-border",
            spacing: 5,
            width: 250,
            backgroundColor: "transparent",
          });
          this.getChildControl("left-side").add(control, {
            flex: 1
          });
          break;
        case "models-details": {
          control = new osparc.vipMarket.LicensedItemDetails().set({
            padding: 5,
          });
          const scrollView = new qx.ui.container.Scroll();
          scrollView.add(control);
          this.bind("openBy", control, "openBy");
          this.getChildControl("right-side").add(scrollView, {
            flex: 1
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("sort-button");
      this.getChildControl("filter-text");
      const modelsUIList = this.getChildControl("models-list");

      const anatomicalModelsModel = this.__anatomicalBundlesModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(anatomicalModelsModel, modelsUIList, "displayName");
      membersCtrl.setDelegate({
        createItem: () => new osparc.vipMarket.LicensedItemListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("key", "key", null, item, id);
          ctrl.bindProperty("version", "version", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("displayName", "displayName", null, item, id);
          ctrl.bindProperty("date", "date", null, item, id);
          ctrl.bindProperty("licensedItemId", "licensedItemId", null, item, id);
          ctrl.bindProperty("pricingPlanId", "pricingPlanId", null, item, id);
          ctrl.bindProperty("seats", "seats", null, item, id);
        },
        configureItem: item => {
          item.subscribeToFilterGroup("vipModels");
        },
      });

      const loadingModel = {
        id: 0,
        thumbnail: "@FontAwesome5Solid/spinner/32",
        name: this.tr("Loading"),
      };
      this.__anatomicalBundlesModel.append(qx.data.marshal.Json.createModel(loadingModel));

      const anatomicModelDetails = this.getChildControl("models-details");

      modelsUIList.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const licensedItemId = selection[0].getLicensedItemId();
          const licensedItemBundle = this.__anatomicalBundles.find(anatomicalBundle => anatomicalBundle.getLicensedItemId() === licensedItemId);
          if (licensedItemBundle) {
            anatomicModelDetails.setAnatomicalModelsData(licensedItemBundle);
            return;
          }
        }
        anatomicModelDetails.setAnatomicalModelsData(null);
      }, this);
    },

    setLicensedItems: function(licensedBundles) {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (!contextWallet) {
        return;
      }

      this.__anatomicalBundles = licensedBundles;

      this.__populateModels();

      const anatomicModelDetails = this.getChildControl("models-details");
      if (!anatomicModelDetails.hasListener("modelPurchaseRequested")) {
        anatomicModelDetails.addListener("modelPurchaseRequested", e => {
          const {
            licensedItemId,
            pricingPlanId,
            pricingUnitId,
          } = e.getData();
          this.__modelPurchaseRequested(licensedItemId, pricingPlanId, pricingUnitId);
        }, this);
      }
      if (!anatomicModelDetails.hasListener("modelImportRequested")) {
        anatomicModelDetails.addListener("modelImportRequested", e => {
          const {
            modelId,
            categoryId,
          } = e.getData();
          this.__sendImportModelMessage(modelId, categoryId);
        }, this);
      }
    },

    __populateModels: function(selectLicensedItemId) {
      const models = this.__anatomicalBundles;

      this.__anatomicalBundlesModel.removeAll();
      const sortModel = sortBy => {
        models.sort((a, b) => {
          // first criteria
          const nASeats = osparc.store.LicensedItems.seatsToNSeats(a.getSeats());
          const nBSeats = osparc.store.LicensedItems.seatsToNSeats(b.getSeats());
          if (nBSeats !== nASeats) {
            // nSeats first
            return nBSeats - nASeats;
          }
          // second criteria
          if (sortBy) {
            if (sortBy["sort"] === "name") {
              if (sortBy["order"] === "down") {
                // A -> Z
                return a.getDisplayName().localeCompare(b.getDisplayName());
              }
              return b.getDisplayName().localeCompare(a.getDisplayName());
            } else if (sortBy["sort"] === "date") {
              if (sortBy["order"] === "down") {
                // Now -> Yesterday
                return b.getDate() - a.getDate();
              }
              return a.getDate() - b.getDate();
            }
          }
          // default criteria
          // A -> Z
          return a.getDisplayName().localeCompare(b.getDisplayName());
        });
      };
      sortModel();
      models.forEach(model => this.__anatomicalBundlesModel.append(qx.data.marshal.Json.createModel(model)));

      this.getChildControl("sort-button").addListener("sortBy", e => {
        this.__anatomicalBundlesModel.removeAll();
        const sortBy = e.getData();
        sortModel(sortBy);
        models.forEach(model => this.__anatomicalBundlesModel.append(qx.data.marshal.Json.createModel(model)));
      }, this);

      // select model after timeout, there is something that changes the selection to empty after populating the list
      setTimeout(() => {
        const modelsUIList = this.getChildControl("models-list");
        if (selectLicensedItemId) {
          const entryFound = modelsUIList.getSelectables().find(entry => "getLicensedItemId" in entry && entry.getLicensedItemId() === selectLicensedItemId);
          modelsUIList.setSelection([entryFound]);
        } else if (modelsUIList.getSelectables().length) {
          // select first
          modelsUIList.setSelection([modelsUIList.getSelectables()[0]]);
        }
      }, 100);
    },

    __modelPurchaseRequested: function(licensedItemId, pricingPlanId, pricingUnitId) {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (!contextWallet) {
        return;
      }
      const walletId = contextWallet.getWalletId();
      let numOfSeats = null;
      const pricingUnit = osparc.store.Pricing.getInstance().getPricingUnit(pricingPlanId, pricingUnitId);
      if (pricingUnit) {
        numOfSeats = parseInt(pricingUnit.getUnitData()["num_of_seats"]);
      }
      const licensedItemsStore = osparc.store.LicensedItems.getInstance();
      licensedItemsStore.purchaseLicensedItem(licensedItemId, walletId, pricingPlanId, pricingUnitId, numOfSeats)
        .then(purchaseData => {
          const nSeats = purchaseData["numOfSeats"];
          let msg = nSeats;
          msg += " seat" + (nSeats > 1 ? "s" : "");
          msg += " rented until " + osparc.utils.Utils.formatDate(new Date(purchaseData["expireAt"]));
          osparc.FlashMessenger.getInstance().logAs(msg, "INFO");

          const found = this.__anatomicalBundles.find(model => model.getLicensedItemId() === licensedItemId);
          if (found) {
            found.getSeats().push({
              licensedItemId: purchaseData["licensedItemId"],
              licensedItemPurchaseId: purchaseData["licensedItemPurchaseId"],
              numOfSeats: purchaseData["numOfSeats"],
              expireAt: new Date(purchaseData["expireAt"]),
            });
            this.__populateModels(licensedItemId);
            const anatomicModelDetails = this.getChildControl("models-details");
            anatomicModelDetails.setAnatomicalModelsData(found);
          }
          this.fireEvent("modelPurchased");
        })
        .catch(err => {
          const msg = err.message || this.tr("Cannot purchase model");
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
    },

    __sendImportModelMessage: function(modelId, categoryId) {
      const store = osparc.store.Store.getInstance();
      const currentStudy = store.getCurrentStudy();
      const nodeId = this.getOpenBy();
      if (currentStudy && nodeId) {
        const msg = {
          "type": "importModel",
          "message": {
            "modelId": modelId,
            "categoryId": categoryId,
          },
        };
        if (currentStudy.sendMessageToIframe(nodeId, msg)) {
          this.fireEvent("importMessageSent");
        }
      }
    },
  }
});

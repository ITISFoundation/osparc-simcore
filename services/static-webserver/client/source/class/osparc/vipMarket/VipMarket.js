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
  extend: qx.ui.core.Widget,

  construct: function(licensedItems) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

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
          });
          this._add(control);
          break;
        case "right-side":
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
            alignY: "middle",
          });
          this._add(control, {
            flex: 1
          });
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
            minWidth: 160,
          });
          control.getChildControl("textfield").set({
            backgroundColor: "transparent",
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
            minWidth: 250,
            maxWidth: 250,
            backgroundColor: "transparent",
          });
          this.getChildControl("left-side").add(control, {
            flex: 1
          });
          break;
        case "models-details": {
          control = new osparc.vipMarket.AnatomicalModelDetails().set({
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
        createItem: () => new osparc.vipMarket.AnatomicalModelListItem(),
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
          const licensedItemBundle = this.__anatomicalBundles.find(anatomicalBundle => anatomicalBundle["licensedItemId"] === licensedItemId);
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

      this.__anatomicalBundles = [];
      licensedBundles.forEach(licensedBundle => {
        licensedBundle["thumbnail"] = "";
        licensedBundle["date"] = null;
        if (licensedBundle["licensedResources"] && licensedBundle["licensedResources"].length) {
          const firstItem = licensedBundle["licensedResources"][0]["source"];
          if (firstItem["thumbnail"]) {
            licensedBundle["thumbnail"] = firstItem["thumbnail"];
          }
          if (firstItem["features"] && firstItem["features"]["date"]) {
            licensedBundle["date"] = new Date(firstItem["features"]["date"]);
          }
        }
        this.__anatomicalBundles.push(licensedBundle);
      });

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
            modelId
          } = e.getData();
          this.__sendImportModelMessage(modelId);
        }, this);
      }
    },

    __populateModels: function(selectLicensedItemId) {
      const models = this.__anatomicalBundles;

      this.__anatomicalBundlesModel.removeAll();
      const sortModel = sortBy => {
        models.sort((a, b) => {
          // first criteria
          const nASeats = osparc.store.LicensedItems.seatsToNSeats(a["seats"]);
          const nBSeats = osparc.store.LicensedItems.seatsToNSeats(b["seats"]);
          if (nBSeats !== nASeats) {
            // nSeats first
            return nBSeats - nASeats;
          }
          // second criteria
          if (sortBy) {
            if (sortBy["sort"] === "name") {
              if (sortBy["order"] === "down") {
                // A -> Z
                return a["displayName"].localeCompare(b["displayName"]);
              }
              return b["displayName"].localeCompare(a["displayName"]);
            } else if (sortBy["sort"] === "date") {
              if (sortBy["order"] === "down") {
                // Now -> Yesterday
                return b["date"] - a["date"];
              }
              return a["date"] - b["date"];
            }
          }
          // default criteria
          // A -> Z
          return a["displayName"].localeCompare(b["displayName"]);
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
        const split = pricingUnit.getName().split(" ");
        numOfSeats = parseInt(split[0]);
      }
      const licensedItemsStore = osparc.store.LicensedItems.getInstance();
      licensedItemsStore.purchaseLicensedItem(licensedItemId, walletId, pricingPlanId, pricingUnitId, numOfSeats)
        .then(purchaseData => {
          let msg = numOfSeats;
          msg += " seat" + (purchaseData["numOfSeats"] > 1 ? "s" : "");
          msg += " rented until " + osparc.utils.Utils.formatDate(new Date(purchaseData["expireAt"]));
          osparc.FlashMessenger.getInstance().logAs(msg, "INFO");

          const found = this.__anatomicalBundles.find(model => model["licensedItemId"] === licensedItemId);
          if (found) {
            found["seats"].push({
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

    __sendImportModelMessage: function(modelId) {
      const store = osparc.store.Store.getInstance();
      const currentStudy = store.getCurrentStudy();
      const nodeId = this.getOpenBy();
      if (currentStudy && nodeId) {
        const msg = {
          "type": "importModel",
          "message": {
            "modelId": modelId,
          },
        };
        if (currentStudy.sendMessageToIframe(nodeId, msg)) {
          this.fireEvent("importMessageSent");
        }
      }
    },
  }
});

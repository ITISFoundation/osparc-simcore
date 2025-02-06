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

  construct: function(anatomicalModels) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    this.__buildLayout();

    if (anatomicalModels) {
      this.setLicensedItems(anatomicalModels);
    }
  },

  events: {
    "importMessageSent": "qx.event.type.Data"
  },

  properties: {
    openBy: {
      check: "String",
      init: null,
      nullable: true,
      event: "changeOpenBy",
    },

    category: {
      check: ["HumanWholeBody", "HumanBodyRegion", "AnimalWholeBody", "ComputationalPhantom"],
      init: null,
      nullable: true,
    },
  },

  members: {
    __anatomicalModels: null,
    __anatomicalModelsModel: null,

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
        case "models-details":
          control = new osparc.vipMarket.AnatomicalModelDetails().set({
            padding: 5,
          });
          this.bind("openBy", control, "openBy");
          this.getChildControl("right-side").add(control, {
            flex: 1
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("sort-button");
      this.getChildControl("filter-text");
      const modelsUIList = this.getChildControl("models-list");

      const anatomicalModelsModel = this.__anatomicalModelsModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(anatomicalModelsModel, modelsUIList, "displayName");
      membersCtrl.setDelegate({
        createItem: () => new osparc.vipMarket.AnatomicalModelListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("modelId", "modelId", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("displayName", "displayName", null, item, id);
          ctrl.bindProperty("date", "date", null, item, id);
          ctrl.bindProperty("licensedItemId", "licensedItemId", null, item, id);
          ctrl.bindProperty("pricingPlanId", "pricingPlanId", null, item, id);
          ctrl.bindProperty("purchases", "purchases", null, item, id);
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
      this.__anatomicalModelsModel.append(qx.data.marshal.Json.createModel(loadingModel));

      const anatomicModelDetails = this.getChildControl("models-details");

      modelsUIList.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const modelId = selection[0].getModelId();
          const modelFound = this.__anatomicalModels.find(anatomicalModel => anatomicalModel["modelId"] === modelId);
          if (modelFound) {
            anatomicModelDetails.setAnatomicalModelsData(modelFound);
            return;
          }
        }
        anatomicModelDetails.setAnatomicalModelsData(null);
      }, this);
    },

    setLicensedItems: function(licensedItems) {
      const store = osparc.store.Store.getInstance();
      const contextWallet = store.getContextWallet();
      if (!contextWallet) {
        return;
      }

      const licensedItemsStore = osparc.store.LicensedItems.getInstance();
      const walletId = contextWallet.getWalletId();
      licensedItemsStore.getPurchasedLicensedItems(walletId)
        .then(purchasesItems => {
          this.__anatomicalModels = [];
          licensedItems.forEach(licensedItem => {
            const anatomicalModel = osparc.utils.Utils.deepCloneObject(licensedItem);
            anatomicalModel["modelId"] = licensedItem["licensedItemId"];
            anatomicalModel["thumbnail"] = "";
            anatomicalModel["date"] = null;
            if (anatomicalModel["licensedResourceData"] && anatomicalModel["licensedResourceData"]["source"]) {
              const anatomicalModelSource = anatomicalModel["licensedResourceData"]["source"];
              if (anatomicalModelSource["thumbnail"]) {
                anatomicalModel["thumbnail"] = anatomicalModelSource["thumbnail"];
              }
              if (anatomicalModelSource["features"] && anatomicalModelSource["features"]["date"]) {
                anatomicalModel["date"] = new Date(anatomicalModelSource["features"]["date"]);
              }
            }
            // attach license data
            anatomicalModel["licensedItemId"] = licensedItem["licensedItemId"];
            anatomicalModel["pricingPlanId"] = licensedItem["pricingPlanId"];
            // attach leased data
            anatomicalModel["purchases"] = []; // default
            const purchasesItemsFound = purchasesItems.filter(purchasesItem => purchasesItem["licensedItemId"] === licensedItem["licensedItemId"]);
            if (purchasesItemsFound.length) {
              purchasesItemsFound.forEach(purchasesItemFound => {
                anatomicalModel["purchases"].push({
                  expiresAt: new Date(purchasesItemFound["expireAt"]),
                  numberOfSeats: purchasesItemFound["numOfSeats"],
                })
              });
            }
            this.__anatomicalModels.push(anatomicalModel);
          });

          this.__populateModels();

          const anatomicModelDetails = this.getChildControl("models-details");
          anatomicModelDetails.addListener("modelPurchaseRequested", e => {
            if (!contextWallet) {
              return;
            }
            const {
              modelId,
              licensedItemId,
              pricingPlanId,
              pricingUnitId,
            } = e.getData();
            let numberOfSeats = null;
            const pricingUnit = osparc.store.Pricing.getInstance().getPricingUnit(pricingPlanId, pricingUnitId);
            if (pricingUnit) {
              const split = pricingUnit.getName().split(" ");
              numberOfSeats = parseInt(split[0]);
            }
            licensedItemsStore.purchaseLicensedItem(licensedItemId, walletId, pricingPlanId, pricingUnitId, numberOfSeats)
              .then(() => {
                const expirationDate = osparc.study.PricingUnitLicense.getExpirationDate();
                const purchaseData = {
                  expiresAt: expirationDate, // get this info from the response
                  numberOfSeats, // get this info from the response
                };

                let msg = numberOfSeats;
                msg += " seat" + (purchaseData["numberOfSeats"] > 1 ? "s" : "");
                msg += " rented until " + osparc.utils.Utils.formatDate(purchaseData["expiresAt"]);
                osparc.FlashMessenger.getInstance().logAs(msg, "INFO");

                const found = this.__anatomicalModels.find(model => model["modelId"] === modelId);
                if (found) {
                  found["purchases"].push(purchaseData);
                  this.__populateModels(modelId);
                  anatomicModelDetails.setAnatomicalModelsData(found);
                }
              })
              .catch(err => {
                const msg = err.message || this.tr("Cannot purchase model");
                osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
              });
          }, this);

          anatomicModelDetails.addListener("modelImportRequested", e => {
            const {
              modelId
            } = e.getData();
            this.__sendImportModelMessage(modelId);
          }, this);
        });
    },

    __populateModels: function(selectModelId) {
      const models = this.__anatomicalModels;

      this.__anatomicalModelsModel.removeAll();
      const sortModel = sortBy => {
        models.sort((a, b) => {
          // first criteria
          const nASeats = osparc.store.LicensedItems.purchasesToNSeats(a["purchases"]);
          const nBSeats = osparc.store.LicensedItems.purchasesToNSeats(b["purchases"]);
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
      models.forEach(model => this.__anatomicalModelsModel.append(qx.data.marshal.Json.createModel(model)));

      this.getChildControl("sort-button").addListener("sortBy", e => {
        this.__anatomicalModelsModel.removeAll();
        const sortBy = e.getData();
        sortModel(sortBy);
        models.forEach(model => this.__anatomicalModelsModel.append(qx.data.marshal.Json.createModel(model)));
      }, this);

      // select model after timeout, there is something that changes the selection to empty after populating the list
      setTimeout(() => {
        const modelsUIList = this.getChildControl("models-list");
        if (selectModelId) {
          const entryFound = modelsUIList.getSelectables().find(entry => "getModelId" in entry && entry.getModelId() === selectModelId);
          modelsUIList.setSelection([entryFound]);
        } else if (modelsUIList.getSelectables().length) {
          // select first
          modelsUIList.setSelection([modelsUIList.getSelectables()[0]]);
        }
      }, 100);
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

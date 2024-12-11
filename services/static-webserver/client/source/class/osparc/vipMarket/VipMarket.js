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

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(10));

    this.__buildLayout();
  },

  properties: {
    metadataUrl: {
      check: "String",
      init: null,
      nullable: false,
      apply: "__fetchModels",
    }
  },

  statics: {
    curateAnatomicalModels: function(anatomicalModelsRaw) {
      const anatomicalModels = [];
      const models = anatomicalModelsRaw["availableDownloads"];
      models.forEach(model => {
        const curatedModel = {};
        Object.keys(model).forEach(key => {
          if (key === "Features") {
            let featuresRaw = model["Features"];
            featuresRaw = featuresRaw.substring(1, featuresRaw.length-1); // remove brackets
            featuresRaw = featuresRaw.split(","); // split the string by commas
            const features = {};
            featuresRaw.forEach(pair => { // each pair is "key: value"
              const keyValue = pair.split(":");
              features[keyValue[0].trim()] = keyValue[1].trim()
            });
            curatedModel["Features"] = features;
          } else {
            curatedModel[key] = model[key];
          }
        });
        anatomicalModels.push(curatedModel);
      });
      return anatomicalModels;
    },
  },

  members: {
    __anatomicalModels: null,
    __purchasedItems: null,
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
            maxWidth: 250
          });
          this.getChildControl("left-side").add(control, {
            flex: 1
          });
          break;
        case "models-details":
          control = new osparc.vipMarket.AnatomicalModelDetails().set({
            padding: 10,
          });
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
      const membersCtrl = new qx.data.controller.List(anatomicalModelsModel, modelsUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.vipMarket.AnatomicalModelListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("modelId", "modelId", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "name", null, item, id);
          ctrl.bindProperty("date", "date", null, item, id);
          ctrl.bindProperty("licensedItemId", "licensedItemId", null, item, id);
          ctrl.bindProperty("pricingPlanId", "pricingPlanId", null, item, id);
          ctrl.bindProperty("purchased", "purchased", null, item, id);
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

    __fetchModels: function(url) {
      fetch(url, {
        method:"POST"
      })
        .then(resp => resp.json())
        .then(anatomicalModelsRaw => {
          const allAnatomicalModels = this.self().curateAnatomicalModels(anatomicalModelsRaw);

          const store = osparc.store.Store.getInstance();
          const contextWallet = store.getContextWallet();
          if (!contextWallet) {
            return;
          }
          const walletId = contextWallet.getWalletId();
          const purchasesParams = {
            url: {
              walletId
            }
          };
          Promise.all([
            osparc.data.Resources.get("market"),
            osparc.data.Resources.fetch("wallets", "purchases", purchasesParams),
          ])
            .then(values => {
              const licensedItems = values[0];
              const purchasedItems = values[1];
              this.__purchasedItems = purchasedItems;

              this.__anatomicalModels = [];
              allAnatomicalModels.forEach(model => {
                const modelId = model["ID"];
                const licensedItem = licensedItems.find(licItem => licItem["name"] == modelId);
                if (licensedItem) {
                  const anatomicalModel = {};
                  anatomicalModel["modelId"] = model["ID"];
                  anatomicalModel["thumbnail"] = model["Thumbnail"];
                  anatomicalModel["name"] = model["Features"]["name"] + " " + model["Features"]["version"];
                  anatomicalModel["description"] = model["Description"];
                  anatomicalModel["features"] = model["Features"];
                  anatomicalModel["date"] = new Date(model["Features"]["date"]);
                  anatomicalModel["DOI"] = model["DOI"];
                  // attach license data
                  anatomicalModel["licensedItemId"] = licensedItem["licensedItemId"];
                  anatomicalModel["pricingPlanId"] = licensedItem["pricingPlanId"];
                  // attach leased data
                  anatomicalModel["purchased"] = null; // default
                  const purchasedItemFound = purchasedItems.find(purchasedItem => purchasedItem["licensedItemId"] === licensedItem["licensedItemId"])
                  if (purchasedItemFound) {
                    anatomicalModel["purchased"] = {
                      expiresAt: new Date(purchasedItemFound["expireAt"]),
                      numberOfSeats: purchasedItemFound["numOfSeats"],
                    }
                  }
                  this.__anatomicalModels.push(anatomicalModel);
                }
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
                const params = {
                  url: {
                    licensedItemId
                  },
                  data: {
                    "wallet_id": walletId,
                    "pricing_plan_id": pricingPlanId,
                    "pricing_unit_id": pricingUnitId,
                    "num_of_seats": 1, // it might not be used
                  },
                }
                osparc.data.Resources.fetch("market", "purchase", params)
                  .then(() => {
                    const found = this.__anatomicalModels.find(model => model["ID"] === modelId);
                    if (found) {
                      found["purchased"] = {
                        expiresAt: new Date(),
                        numberOfSeats: 1,
                      };
                      this.__populateModels();
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
                console.log("Import", modelId);
              }, this);
            });
        })
        .catch(err => console.error(err));
    },

    __populateModels: function() {
      const models = this.__anatomicalModels;

      this.__anatomicalModelsModel.removeAll();
      const sortModel = sortBy => {
        models.sort((a, b) => {
          // first criteria
          if (Boolean(b["purchased"]) !== Boolean(a["purchased"])) {
            // leased first
            return Boolean(b["purchased"]) - Boolean(a["purchased"]);
          }
          // second criteria
          if (sortBy) {
            if (sortBy["sort"] === "name") {
              if (sortBy["order"] === "down") {
                // A -> Z
                return a["name"].localeCompare(b["name"]);
              }
              return b["name"].localeCompare(a["name"]);
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
          return a["name"].localeCompare(b["name"]);
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
    },
  }
});

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
          if (key === "ID") {
            curatedModel["purchased"] = model["ID"] < 4;
          }
        });
        anatomicalModels.push(curatedModel);
      });
      return anatomicalModels;
    },
  },

  members: {
    __anatomicalModels: null,
    __licensedItems: null,
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

          osparc.data.Resources.get("market")
            .then(licensedItems => {
              this.__licensedItems = licensedItems;

              this.__anatomicalModels = [];
              allAnatomicalModels.forEach(model => {
                const modelId = model["ID"];
                const licensedItem = this.__licensedItems.find(licItem => licItem["name"] == modelId);
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
                  anatomicalModel["purchased"] = model["purchased"];
                  this.__anatomicalModels.push(anatomicalModel);
                }
              });

              this.__populateModels();

              const anatomicModelDetails = this.getChildControl("models-details");
              anatomicModelDetails.addListener("modelPurchaseRequested", e => {
                const {
                  modelId,
                  licensedItemId,
                  pricingUnitId,
                } = e.getData();
                console.log("purchase", licensedItemId, pricingUnitId);
                const found = this.__anatomicalModels.find(model => model["ID"] === modelId);
                if (found) {
                  found["purchased"] = true;
                  this.__populateModels();
                  anatomicModelDetails.setAnatomicalModelsData(found);
                }
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
          if (b["purchased"] !== a["purchased"]) {
            // leased first
            return b["purchased"] - a["purchased"];
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

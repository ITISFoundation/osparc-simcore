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

    this._setLayout(new qx.ui.layout.VBox(10));

    this.__buildLayout();
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
            curatedModel["leased"] = [22].includes(model[key]);
          }
        });
        anatomicalModels.push(curatedModel);
      });
      return anatomicalModels;
    },
  },

  members: {
    __anatomicalModelsModel: null,
    __anatomicalModels: null,
    __sortByButton: null,

    __buildLayout: function() {
      const toolbarLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        alignY: "middle",
      });
      this._add(toolbarLayout);

      const sortModelsButtons = this.__sortByButton = new osparc.vipMarket.SortModelsButtons().set({
        alignY: "bottom",
        maxHeight: 27,
      });
      toolbarLayout.add(sortModelsButtons);

      const filter = new osparc.filter.TextFilter("text", "vipModels").set({
        alignY: "middle",
        allowGrowY: false,
        minWidth: 170,
      });
      this.addListener("appear", () => filter.getChildControl("textfield").focus());
      toolbarLayout.add(filter);

      const modelsLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
      this._add(modelsLayout, {
        flex: 1
      });
      
      const modelsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 5,
        minWidth: 250,
        maxWidth: 250
      });
      modelsLayout.add(modelsUIList)

      const anatomicalModelsModel = this.__anatomicalModelsModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(anatomicalModelsModel, modelsUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.vipMarket.AnatomicalModelListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "modelId", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "name", null, item, id);
          ctrl.bindProperty("date", "date", null, item, id);
          ctrl.bindProperty("leased", "leased", null, item, id);
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

      const anatomicModelDetails = new osparc.vipMarket.AnatomicalModelDetails().set({
        padding: 20,
      });
      modelsLayout.add(anatomicModelDetails, {
        flex: 1
      });

      modelsUIList.addListener("changeSelection", e => {
        const selection = e.getData();
        if (selection.length) {
          const modelId = selection[0].getModelId();
          const modelFound = this.__anatomicalModels.find(anatomicalModel => anatomicalModel["ID"] === modelId);
          if (modelFound) {
            anatomicModelDetails.setAnatomicalModelsData(modelFound);
            return;
          }
        }
        anatomicModelDetails.setAnatomicalModelsData(null);
      }, this);

      fetch("https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnatomicalModels", {
        method:"POST"
      })
        .then(resp => resp.json())
        .then(anatomicalModelsRaw => {
          this.__anatomicalModels = this.self().curateAnatomicalModels(anatomicalModelsRaw);
          this.__populateModels();

          anatomicModelDetails.addListener("modelLeased", e => {
            const modelId = e.getData();
            const found = this.__anatomicalModels.find(model => model["ID"] === modelId);
            if (found) {
              found["leased"] = true;
              this.__populateModels();
              anatomicModelDetails.setAnatomicalModelsData(found);
            };
          }, this);
        })
        .catch(err => console.error(err));
    },

    __populateModels: function() {
      const models = [];
      this.__anatomicalModels.forEach(model => {
        const anatomicalModel = {};
        anatomicalModel["id"] = model["ID"];
        anatomicalModel["thumbnail"] = model["Thumbnail"];
        anatomicalModel["name"] = model["Features"]["name"] + " " + model["Features"]["version"];
        anatomicalModel["date"] = new Date(model["Features"]["date"]);
        anatomicalModel["leased"] = model["leased"];
        models.push(anatomicalModel);
      });

      this.__anatomicalModelsModel.removeAll();
      const sortModel = sortBy => {
        models.sort((a, b) => {
          // first criteria
          if (b["leased"] !== a["leased"]) {
            // leased first
            return b["leased"] - a["leased"];
          }
          // second criteria
          if (sortBy) {
            if (sortBy["sort"] === "name") {
              if (sortBy["order"] === "down") {
                // A -> Z
                return a["name"].localeCompare(b["name"]);
              } else {
                return b["name"].localeCompare(a["name"]);
              }
            } else if (sortBy["sort"] === "date") {
              if (sortBy["order"] === "down") {
                // Now -> Yesterday
                return b["date"] - a["date"];
              } else {
                return a["date"] - b["date"];
              }
            }
          }
          // default criteria
          // A -> Z
          return a["name"].localeCompare(b["name"]);
        });
      };
      sortModel();
      models.forEach(model => this.__anatomicalModelsModel.append(qx.data.marshal.Json.createModel(model)));

      this.__sortByButton.addListener("sortBy", e => {
        this.__anatomicalModelsModel.removeAll();
        const sortBy = e.getData();
        sortModel(sortBy);
        models.forEach(model => this.__anatomicalModelsModel.append(qx.data.marshal.Json.createModel(model)));
      }, this);
    },
  }
});

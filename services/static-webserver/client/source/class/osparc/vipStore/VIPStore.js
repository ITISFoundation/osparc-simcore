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

qx.Class.define("osparc.vipStore.VIPStore", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("VIP Store"));

    this.set({
      layout: new qx.ui.layout.VBox(10),
      minWidth: this.self().MAX_WIDTH,
      minHeight: this.self().MAX_HEIGHT,
      contentPadding: this.self().PADDING,
      resizable: true,
      showMaximize: false,
      showMinimize: false,
      centerOnAppear: true,
      clickAwayClose: true,
      modal: true
    });
    const closeBtn = this.getChildControl("close-button");
    osparc.utils.Utils.setIdToWidget(closeBtn, "vipStoreWindowCloseBtn");

    this.__buildLayout();
  },

  statics: {
    MAX_WIDTH: 900,
    MAX_HEIGHT: 700,
    PADDING: 15,

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
    __anatomicalModelsModel: null,
    __anatomicalModels: null,

    __buildLayout: async function() {
      this._removeAll();

      const toolbarLayout = new qx.ui.container.Composite(new qx.ui.layout.HBox(10)).set({
        maxHeight: 30
      });
      this._add(toolbarLayout);

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
        createItem: () => new osparc.vipStore.AnatomicalModelListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "modelId", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "name", null, item, id);
          ctrl.bindProperty("date", "date", null, item, id);
        },
      });

      const anatomicModelDetails = new osparc.vipStore.AnatomicalModelDetails().set({
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

      // fetch data
      const resp = await fetch("https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnatomicalModels", {method:"POST"});
      const anatomicalModelsRaw = await resp.json();
      this.__anatomicalModels = this.self().curateAnatomicalModels(anatomicalModelsRaw);
      this.__populateModels();
    },

    __populateModels: function() {
      const anatomicalModelsModel = this.__anatomicalModelsModel;
      anatomicalModelsModel.removeAll();
        
      this.__anatomicalModels.forEach(model => {
        const anatomicalModel = {};
        anatomicalModel["id"] = model["ID"];
        anatomicalModel["thumbnail"] = model["Thumbnail"];
        anatomicalModel["name"] = model["Features"]["name"];
        anatomicalModel["date"] = new Date(model["Features"]["date"]);
        anatomicalModelsModel.append(qx.data.marshal.Json.createModel(anatomicalModel));
      });
    },
  }
});

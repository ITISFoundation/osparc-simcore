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
      layout: new qx.ui.layout.HBox(10),
      maxWidth: this.self().MAX_WIDTH,
      maxHeight: this.self().MAX_HEIGHT,
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
  },

  members: {
    __anatomicalModelsRaw: null,
    __anatomicalModelsModel: null,

    __buildLayout: async function() {
      const modelsUIList = new qx.ui.form.List().set({
        decorator: "no-border",
        spacing: 3,
        width: 250
      });
      this._add(modelsUIList)

      const anatomicalModelsModel = this.__anatomicalModelsModel = new qx.data.Array();
      const membersCtrl = new qx.data.controller.List(anatomicalModelsModel, modelsUIList, "name");
      membersCtrl.setDelegate({
        createItem: () => new osparc.vipStore.AnatomicModelListItem(),
        bindItem: (ctrl, item, id) => {
          ctrl.bindProperty("id", "modelId", null, item, id);
          ctrl.bindProperty("thumbnail", "thumbnail", null, item, id);
          ctrl.bindProperty("name", "name", null, item, id);
          ctrl.bindProperty("date", "date", null, item, id);
        },
      });

      // fetch data
      const resp = await fetch("https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnatomicalModels", {method:"POST"});
      const anatomicalModelsRaw = await resp.json();
      this.__populateModels(anatomicalModelsRaw);
    },

    __populateModels: function(anatomicalModelsRaw) {
      const anatomicalModels = this.__anatomicalModels = anatomicalModelsRaw["availableDownloads"];

      const anatomicalModelsModel = this.__anatomicalModelsModel;
      anatomicalModelsModel.removeAll();

      anatomicalModels.forEach(anatomicalModelData => {
        // this is a JSON but it's missing the quotes
        let featuresRaw = anatomicalModelData["Features"];
        featuresRaw = featuresRaw.substring(1, featuresRaw.length-1); // remove brackets
        featuresRaw = featuresRaw.split(","); // split the string by commas
        const features = {};
        featuresRaw.forEach(pair => { // each pair is "key: value"
          const keyValue = pair.split(":");
          features[keyValue[0].trim()] = keyValue[1].trim()
        });
        
        const anatomicalModel = {};
        anatomicalModel["id"] = anatomicalModelData["ID"];
        anatomicalModel["thumbnail"] = anatomicalModelData["Thumbnail"];
        anatomicalModel["name"] = features["name"];
        anatomicalModel["date"] = new Date(features["date"]);
        anatomicalModelsModel.append(qx.data.marshal.Json.createModel(anatomicalModel));
      });
    },
  }
});

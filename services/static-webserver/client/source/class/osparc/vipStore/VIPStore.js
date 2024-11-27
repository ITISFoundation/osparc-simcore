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

qx.Class.define("osparc.vipCenter.VIPStore", {
  extend: osparc.ui.window.Window,
  type: "singleton",

  construct: function() {
    this.base(arguments, this.tr("VIP Store"));

    this.set({
      layout: new qx.ui.layout.VBox(10),
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
    MAX_WIDTH: 700,
    MAX_HEIGHT: 700,
    PADDING: 15,
  },

  members: {
    __dummyViewer: null,
    __anatomicalModelsRaw: null,

    __buildLayout: async function() {
      this.__dummyViewer = new osparc.ui.basic.JsonTreeWidget();
      this._add(this.__dummyViewer);

      // fetch data
      const resp = await fetch("https://itis.swiss/PD_DirectDownload/getDownloadableItems/AnatomicalModels", {method:"POST"});
      const anatomicalModelsRaw = this.__anatomicalModelsRaw = await resp.json();
      this.__populateModels(anatomicalModelsRaw);
    },

    __populateModels: function(anatomicalModels) {
      this.__dummyViewer.setData(anatomicalModels);
    },
  }
});

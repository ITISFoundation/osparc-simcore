/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.editor.ThumbnailSuggestions", {
  extend: osparc.widget.SlideBar,

  construct: function(study) {
    this.base(arguments);

    this.set({
      alignX: "center",
      maxHeight: 170
    });
    this.setButtonsWidth(30);

    this.__thumbnails = [];

    if (study) {
      this.setStudy(study);
    }
  },

  events: {
    "thumbnailAdded": "qx.event.type.Event",
    "thumbnailTapped": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      nullable: false,
      init: null,
      apply: "__applyStudyData"
    }
  },

  statics: {
    extractThumbnailSuggestions: function(study) {
      const suggestions = new Set([]);
      const wb = study.getWorkbench();
      const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
      Object.values(nodes).forEach(node => {
        const srvMetadata = osparc.service.Utils.getMetaData(node["key"], node["version"]);
        if (srvMetadata && srvMetadata["thumbnail"] && !osparc.data.model.Node.isFrontend(node)) {
          suggestions.add(srvMetadata["thumbnail"]);
        }
      });
      return Array.from(suggestions);
    }
  },

  members: {
    __thumbnails: null,

    __addThumbnail: function(thumbnailData) {
      this.__thumbnails.push(thumbnailData);
      this.fireEvent("thumbnailAdded");
    },

    __applyStudyData: function(study) {
      const wb = study.getWorkbench();
      const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
      Object.values(nodes).forEach(node => {
        const srvMetadata = osparc.service.Utils.getMetaData(node.getKey(), node.getVersion());
        if (srvMetadata && srvMetadata["thumbnail"] && !osparc.data.model.Node.isFrontend(node)) {
          this.__addThumbnail({
            type: "serviceImage",
            thumbnailUrl: srvMetadata["thumbnail"],
            fileUrl: srvMetadata["thumbnail"]
          });
        }
      });
      this.__reloadSuggestions();
    },

    addWorkbenchUIPreviewToSuggestions: function() {
      this.__addThumbnail({
        type: "workbenchUIPreview",
        thumbnailUrl: osparc.product.Utils.getWorkbenchUIPreviewPath(),
        fileUrl: osparc.product.Utils.getWorkbenchUIPreviewPath()
      });
      this.__reloadSuggestions();

      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => this.addWorkbenchUIPreviewToSuggestions());
    },

    addPreviewsToSuggestions: function(previewsPerNodes) {
      previewsPerNodes.forEach(previewsPerNode => {
        const previews = previewsPerNode["screenshots"];
        if (previews && previews.length) {
          previews.forEach(preview => {
            this.__addThumbnail({
              type: preview["mimetype"],
              thumbnailUrl: preview["thumbnail_url"],
              fileUrl: preview["file_url"]
            });
          });
          this.__reloadSuggestions();
        }
      });
    },

    __reloadSuggestions: function() {
      this.setSuggestions(this.__thumbnails);
    },

    thumbnailTapped: function(thumbnail) {
      this.getChildren().forEach(thumbnailImg => osparc.utils.Utils.removeBorder(thumbnailImg));
      osparc.utils.Utils.addBorder(thumbnail, 1, "#007fd4"); // Visual Studio blue
      this.fireDataEvent("thumbnailTapped", {
        type: thumbnail.thumbnailType,
        source: thumbnail.thumbnailFileUrl
      });
    },

    setSuggestions: function(suggestions) {
      this.removeAll();
      suggestions.forEach(suggestion => {
        const maxHeight = this.getMaxHeight();
        const thumbnail = new osparc.ui.basic.Thumbnail(suggestion["thumbnailUrl"], maxHeight, parseInt(maxHeight*2/3));
        thumbnail.thumbnailType = suggestion["type"];
        thumbnail.thumbnailFileUrl = suggestion["fileUrl"];
        thumbnail.setMarginLeft(1); // give some extra space to the selection border
        thumbnail.addListener("tap", () => this.thumbnailTapped(thumbnail), this);
        this.add(thumbnail);
      });
    }
  }
});

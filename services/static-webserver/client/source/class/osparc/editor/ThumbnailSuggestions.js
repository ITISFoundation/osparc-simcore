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

    this.__thumbnailsPerNode = {};

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
    __thumbnailsPerNode: null,

    __applyStudyData: function(study) {
      const wb = study.getWorkbench();
      const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
      Object.values(nodes).forEach(node => {
        const srvMetadata = osparc.service.Utils.getMetaData(node.getKey(), node.getVersion());
        if (srvMetadata && srvMetadata["thumbnail"] && !osparc.data.model.Node.isFrontend(node)) {
          const nodeId = node.getNodeId();
          this.__addThumbnail(nodeId, {
            type: "serviceImage",
            thumbnailUrl: srvMetadata["thumbnail"],
            fileUrl: srvMetadata["thumbnail"]
          });
        }
      });
    },

    __addThumbnail: function(nodeId, thumbnailData) {
      if (!(nodeId in this.__thumbnailsPerNode)) {
        this.__thumbnailsPerNode[nodeId] = [];
      }
      this.__thumbnailsPerNode[nodeId].push(thumbnailData);
      this.fireEvent("thumbnailAdded");
    },

    addWorkbenchUIPreviewToSuggestions: function() {
      this.__addThumbnail("0000-workbenchUIPreview", {
        type: "workbenchUIPreview",
        thumbnailUrl: osparc.product.Utils.getWorkbenchUIPreviewPath(),
        fileUrl: osparc.product.Utils.getWorkbenchUIPreviewPath()
      });

      const themeManager = qx.theme.manager.Meta.getInstance();
      themeManager.addListener("changeTheme", () => this.addWorkbenchUIPreviewToSuggestions());
    },

    addPreviewsToSuggestions: function(previewsPerNodes) {
      previewsPerNodes.forEach(previewsPerNode => {
        const nodeId = previewsPerNode["node_id"];
        const previews = previewsPerNode["screenshots"];
        if (previews && previews.length) {
          previews.forEach(preview => {
            this.__addThumbnail(nodeId, {
              type: preview["mimetype"],
              thumbnailUrl: preview["thumbnail_url"],
              fileUrl: preview["file_url"]
            });
          });
        }
      });
      this.setSelectedNodeId(null);
    },

    setSelectedNodeId: function(selectedNodeId) {
      let suggestions = new Set([]);
      if (selectedNodeId && selectedNodeId in this.__thumbnailsPerNode) {
        const nodeThumbnails = this.__thumbnailsPerNode[selectedNodeId];
        nodeThumbnails.forEach(nodeThumbnail => suggestions.add(nodeThumbnail));
      } else {
        Object.values(this.__thumbnailsPerNode).forEach(nodeThumbnails => {
          nodeThumbnails.forEach(nodeThumbnail => suggestions.add(nodeThumbnail));
        });
      }
      suggestions = Array.from(suggestions);
      this.setSuggestions(suggestions);
    },

    setSuggestions: function(suggestions) {
      this.removeAll();
      suggestions.forEach(suggestion => {
        const maxHeight = this.getMaxHeight();
        const thumbnail = new osparc.ui.basic.Thumbnail(suggestion.thumbnailUrl, maxHeight, parseInt(maxHeight*2/3));
        thumbnail.setMarginLeft(1); // give some extra space to the selection border
        thumbnail.addListener("tap", () => {
          this.getChildren().forEach(thumbnailImg => osparc.utils.Utils.removeBorder(thumbnailImg));
          osparc.utils.Utils.addBorder(thumbnail, 1, "#007fd4"); // Visual Studio blue
          this.fireDataEvent("thumbnailTapped", {
            type: suggestion.type,
            source: suggestion.fileUrl
          });
        }, this);
        this.add(thumbnail);
      });
    }
  }
});

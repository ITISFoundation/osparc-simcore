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

qx.Class.define("osparc.component.editor.ThumbnailSuggestions", {
  extend: osparc.component.widget.SlideBar,

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

  members: {
    __thumbnailsPerNode: null,

    __applyStudyData: function(study) {
      const wb = study.getWorkbench();
      const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
      Object.values(nodes).forEach(node => {
        const srvMetadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
        if (srvMetadata && srvMetadata["thumbnail"] && !osparc.data.model.Node.isFrontend(node)) {
          const nodeId = node["nodeId"];
          if (!(nodeId in this.__thumbnailsPerNode)) {
            this.__thumbnailsPerNode[nodeId] = [];
          }
          this.__thumbnailsPerNode[nodeId].push(srvMetadata["thumbnail"]);
        }
      });
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
        const thumbnail = new osparc.ui.basic.Thumbnail(suggestion, 170, 124);
        thumbnail.addListener("tap", () => {
          this.getChildren().forEach(thumbnailImg => osparc.utils.Utils.removeBorder(thumbnailImg));
          osparc.utils.Utils.addBorder(thumbnail, 1, "#007fd4"); // Visual Studio blue
          this.fireDataEvent("thumbnailTapped", thumbnail.getChildControl("image").getSource());
        });
        this.add(thumbnail);
      });
    }
  }
});

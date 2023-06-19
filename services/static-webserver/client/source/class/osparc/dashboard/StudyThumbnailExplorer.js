/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.StudyThumbnailExplorer", {
  extend: qx.ui.core.Widget,

  construct: function(studyData) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox(5));

    this.__studyData = studyData;

    this.__buildLayout();
    this.__attachEventHandlers();
    this.__initComponents();
  },

  members: {
    __studyData: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "nodes-tree":
          control = this.__getNodesTree().set({
            backgroundColor: "transparent",
            minWidth: 150,
            maxWidth: 150,
            minHeight: 200
          });
          this._add(control);
          break;
        case "thumbnails-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "scroll-thumbnails": {
          control = this.__getThumbnailSuggestions();
          const thumbnailsLayout = this.getChildControl("thumbnails-layout");
          thumbnailsLayout.add(control);
          break;
        }
        case "thumbnail-viewer-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
            maxHeight: 300
          });
          const thumbnailsLayout = this.getChildControl("thumbnails-layout");
          thumbnailsLayout.add(control, {
            flex: 1
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __getNodesTree: function() {
      const study = new osparc.data.model.Study(this.__studyData);
      study.buildWorkbench();
      const nodesTree = new osparc.component.widget.NodesTree().set({
        hideRoot: false,
        simpleNodes: true
      });
      nodesTree.setStudy(study);
      return nodesTree;
    },

    __getThumbnailSuggestions: function() {
      const study = new osparc.data.model.Study(this.__studyData);
      study.buildWorkbench();
      const thumbnailSuggestions = new osparc.component.editor.ThumbnailSuggestions().set({
        maxHeight: 60
      });
      thumbnailSuggestions.setStudy(study);
      return thumbnailSuggestions;
    },

    __buildLayout: function() {
      this.getChildControl("nodes-tree");
      this.getChildControl("scroll-thumbnails");
      this.getChildControl("thumbnail-viewer-layout");
    },

    __attachEventHandlers: function() {
      const nodesTree = this.getChildControl("nodes-tree");
      const scrollThumbnails = this.getChildControl("scroll-thumbnails");
      nodesTree.addListener("changeSelectedNode", e => {
        const selectedNodeId = e.getData();
        scrollThumbnails.setSelectedNodeId(selectedNodeId);
      });
      const thumbnailViewerLayout = this.getChildControl("thumbnail-viewer-layout");
      scrollThumbnails.addListener("thumbnailTapped", e => {
        const thumbnailSource = e.getData();
        thumbnailViewerLayout.removeAll();
        const maxHeight = 300;
        const thumbnail = new osparc.ui.basic.Thumbnail(thumbnailSource, maxHeight, parseInt(maxHeight*2/3));
        thumbnailViewerLayout.add(thumbnail, {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        });
      });
    },

    __initComponents: function() {
      const scrollThumbnails = this.getChildControl("scroll-thumbnails");
      scrollThumbnails.setSelectedNodeId(null);
    }
  }
});

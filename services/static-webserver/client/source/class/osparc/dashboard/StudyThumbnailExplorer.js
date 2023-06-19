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

    this.set({
      minHeight: this.self().LAYOUT_HEIGHT,
      maxHeight: this.self().LAYOUT_HEIGHT
    });

    this.__studyData = studyData;

    this.__buildLayout();
    this.__attachEventHandlers();
    this.__initComponents();
  },

  statics: {
    LAYOUT_HEIGHT: 300,
    NODES_TREE_WIDTH: 160,
    THUMBNAIL_SLIDER_HEIGHT: 45
  },

  members: {
    __studyData: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "nodes-tree":
          control = this.__getNodesTree().set({
            backgroundColor: "transparent",
            minWidth: this.self().NODES_TREE_WIDTH,
            maxWidth: this.self().NODES_TREE_WIDTH,
            maxHeight: this.self().LAYOUT_HEIGHT,
            marginLeft: -20
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
            maxHeight: this.self().LAYOUT_HEIGHT - this.self().THUMBNAIL_SLIDER_HEIGHT
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
        minHeight: this.self().THUMBNAIL_SLIDER_HEIGHT,
        maxHeight: this.self().THUMBNAIL_SLIDER_HEIGHT
      });
      thumbnailSuggestions.setStudy(study);
      return thumbnailSuggestions;
    },

    __getWorkbenchUIPreview: function() {
      const study = new osparc.data.model.Study(this.__studyData);
      study.buildWorkbench();
      const workbenchUIPreview = new osparc.component.workbench.WorkbenchUIPreview();
      workbenchUIPreview.setStudy(study);
      workbenchUIPreview.loadModel(study.getWorkbench());
      // eslint-disable-next-line no-underscore-dangle
      workbenchUIPreview._fitScaleToNodes(0.5);
      return workbenchUIPreview;
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
        const maxHeight = this.self().LAYOUT_HEIGHT - this.self().THUMBNAIL_SLIDER_HEIGHT;
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

      const workbenchUIPreview = this.__getWorkbenchUIPreview();
      const thumbnailViewerLayout = this.getChildControl("thumbnail-viewer-layout");
      thumbnailViewerLayout.add(workbenchUIPreview);
    }
  }
});

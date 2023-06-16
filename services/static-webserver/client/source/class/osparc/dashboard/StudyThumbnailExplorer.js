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
  },

  members: {
    __studyData: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "nodes-tree":
          control = this.__getNodesTree();
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
          control = new osparc.component.widget.SlideBar().set({
            alignX: "center",
            maxHeight: 170
          });
          control.setHeight(100);
          control.setButtonsWidth(30);
          const thumbnailsLayout = this.getChildControl("thumbnails-layout");
          thumbnailsLayout.add(control);
          break;
        }
        case "selected-thumbnail-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Canvas());
          const thumbnailsLayout = this.getChildControl("thumbnails-layout");
          thumbnailsLayout.add(control, {
            flex: 1
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      this.getChildControl("nodes-tree");
    },

    __getNodesTree: function() {
      const study = new osparc.data.model.Study(this.__studyData);
      study.buildWorkbench();
      const nodesTree = new osparc.component.widget.NodesTree().set({
        hideRoot: false,
        backgroundColor: "transparent",
        simpleNodes: true,
        minWidth: 200,
        minHeight: 200
      });
      nodesTree.setStudy(study);
      return nodesTree;
    }
  }
});

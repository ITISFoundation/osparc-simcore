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

    const study = this.__study = new osparc.data.model.Study(studyData);
    // make nodes not movable
    study.setReadOnly(true);

    this.__buildLayout();
    this.__initComponents();
  },

  statics: {
    LAYOUT_HEIGHT: 320,
  },

  members: {
    __study: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "thumbnails-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
          this._add(control, {
            flex: 1
          });
          break;
        }
        case "thumbnail-viewer-layout": {
          control = new qx.ui.container.Composite(new qx.ui.layout.Canvas()).set({
            maxHeight: this.self().LAYOUT_HEIGHT
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

    __buildLayout: function() {
      this.getChildControl("thumbnail-viewer-layout");
    },

    __showInThumbnailViewer: function(type, source) {
      let control = null;
      switch (type) {
        case "workbenchUIPreview":
          control = this.__getWorkbenchUIPreview();
          break;
        default:
          break;
      }
      if (control) {
        const thumbnailViewerLayout = this.getChildControl("thumbnail-viewer-layout");
        thumbnailViewerLayout.removeAll();
        thumbnailViewerLayout.add(control, {
          top: 0,
          right: 0,
          bottom: 0,
          left: 0
        });
      }
    },

    __getWorkbenchUIPreview: function() {
      const workbenchUIPreview = new osparc.workbench.WorkbenchUIPreview();
      workbenchUIPreview.setStudy(this.__study);
      workbenchUIPreview.loadModel(this.__study.getWorkbench());
      workbenchUIPreview.addListener("appear", () => {
        // give it some time to take the bounds
        setTimeout(() => {
          const maxScale = 0.5;
          // eslint-disable-next-line no-underscore-dangle
          workbenchUIPreview._fitScaleToNodes(maxScale);
        }, 300);
      });
      return workbenchUIPreview;
    },

    __initComponents: function() {
      if (this.__isWorkbenchUIPreviewVisible()) {
        this.__showInThumbnailViewer("workbenchUIPreview");
      }
    },

    __isWorkbenchUIPreviewVisible: function() {
      return !["guided", "app"].includes(this.__study.getUi().getMode());
    }
  }
});

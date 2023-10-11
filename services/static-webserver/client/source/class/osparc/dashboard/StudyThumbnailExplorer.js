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
    this.__attachEventHandlers();
    this.__initComponents();
  },

  statics: {
    LAYOUT_HEIGHT: 320,
    THUMBNAIL_SLIDER_HEIGHT: 60
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
        case "thumbnail-suggestions": {
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

    __getThumbnailSuggestions: function() {
      const thumbnailSuggestions = new osparc.editor.ThumbnailSuggestions().set({
        minHeight: this.self().THUMBNAIL_SLIDER_HEIGHT,
        maxHeight: this.self().THUMBNAIL_SLIDER_HEIGHT
      });
      return thumbnailSuggestions;
    },

    __buildLayout: function() {
      this.getChildControl("thumbnail-suggestions");
      this.getChildControl("thumbnail-viewer-layout");
    },

    __attachEventHandlers: function() {
      const scrollThumbnails = this.getChildControl("thumbnail-suggestions");
      scrollThumbnails.addListener("thumbnailTapped", e => {
        const thumbnailData = e.getData();
        this.__showInThumbnailViewer(thumbnailData["type"], thumbnailData["source"]);
      });
    },

    __showInThumbnailViewer: function(type, source) {
      let control = null;
      switch (type) {
        case "workbenchUIPreview":
          control = this.__getWorkbenchUIPreview();
          break;
        case null:
          control = new osparc.widget.Three(source);
          break;
        default:
          control = this.__getThumbnail(source);
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

    __getThumbnail: function(thumbnailSource) {
      const maxHeight = this.self().LAYOUT_HEIGHT - this.self().THUMBNAIL_SLIDER_HEIGHT;
      const thumbnail = new osparc.ui.basic.Thumbnail(thumbnailSource, maxHeight, parseInt(maxHeight*2/3));
      return thumbnail;
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
        }, 50);
      });
      return workbenchUIPreview;
    },

    __initComponents: function() {
      const thumbnailSuggestions = this.getChildControl("thumbnail-suggestions");
      // make it visible only if there are thumbnails
      this.exclude();
      thumbnailSuggestions.addListener("thumbnailAdded", () => this.show());

      if (this.__isWorkbenchUIPreviewVisible()) {
        thumbnailSuggestions.addWorkbenchUIPreviewToSuggestions();
      }

      thumbnailSuggestions.setStudy(this.__study);

      if (this.__isWorkbenchUIPreviewVisible()) {
        this.__showInThumbnailViewer("workbenchUIPreview");
      }

      const params = {
        url: {
          studyId: this.__study.getUuid()
        }
      };
      osparc.data.Resources.fetch("studyPreviews", "getPreviews", params)
        .then(previewsPerNodes => {
          thumbnailSuggestions.addPreviewsToSuggestions(previewsPerNodes);
          // show the last preview by default
          const thumbnails = thumbnailSuggestions.getChildren();
          if (thumbnails && thumbnails.length) {
            thumbnailSuggestions.thumbnailTapped(thumbnails[thumbnails.length-1]);
          }
        })
        .catch(err => console.error(err));
    },

    __isWorkbenchUIPreviewVisible: function() {
      return !["guided", "app"].includes(this.__study.getUi().getMode());
    }
  }
});

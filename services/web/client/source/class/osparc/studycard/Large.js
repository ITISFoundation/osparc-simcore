/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.studycard.Large", {
  extend: qx.ui.core.Widget,

  /**
    * @param studyData {Object} Serialized Study Object
    */
  construct: function(studyData) {
    this.base(arguments);

    this.set({
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(5));

    if (studyData && studyData instanceof Object) {
      this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
    }

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
  },

  events: {
    "updateStudy": "qx.event.type.Data",
    "updateTags": "qx.event.type.Data"
  },

  statics: {
    PADDING: 5,
    EXTRA_INFO_WIDTH: 250,
    THUMBNAIL_MIN_WIDTH: 150,
    THUMBNAIL_MAX_WIDTH: 230
  },

  members: {
    __studyData: null,

    checkResize: function(bounds) {
      this.__rebuildLayout(bounds.width);
    },

    __setUpdatedData: function(studyData) {
      if (studyData && studyData instanceof Object) {
        this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
        this.__rebuildLayout();
      }
    },

    __updateFromCacheAndNotify: function(studyId) {
      const params = {
        url: {
          "projectId": studyId
        }
      };
      osparc.data.Resources.getOne("studies", params, studyId, true)
        .then(studyData => {
          this.fireDataEvent("updateStudy", studyData);
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", studyData);
          this.__setUpdatedData(studyData);
        });
    },

    __isOwner: function() {
      return osparc.data.model.Study.isOwner(this.__studyData);
    },

    __rebuildLayout: function(width) {
      this._removeAll();

      const title = this.__createTitle();
      const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
      this._add(titleLayout);

      const extraInfo = this.__extraInfo();

      let editThumbnailBtn = null;
      if (this.__isOwner()) {
        editThumbnailBtn = osparc.utils.Utils.getEditButton();
        editThumbnailBtn.addListener("execute", () => {
          this.__openThumbnailEditor();
        }, this);
      }
      const bounds = this.getBounds();
      let widgetWidth = null;
      const offset = 30;
      if (width) {
        widgetWidth = width - offset;
      } else if (bounds) {
        widgetWidth = bounds.width - offset;
      } else {
        widgetWidth = 500 - offset;
      }
      let thumbnailWidth = widgetWidth - 2*this.self().PADDING;
      const slim = widgetWidth < this.self().EXTRA_INFO_WIDTH + this.self().THUMBNAIL_MIN_WIDTH + 2*this.self().PADDING - 20;
      if (slim) {
        this._add(extraInfo);
        thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth);
        if (editThumbnailBtn) {
          const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
            alignX: "center"
          }));
          hBox.add(thumbnail, {
            flex: 1
          });
          hBox.add(editThumbnailBtn);
          this._add(hBox);
        } else {
          this._add(thumbnail);
        }
      } else {
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center"
        }));
        hBox.add(extraInfo);
        thumbnailWidth -= this.self().EXTRA_INFO_WIDTH;
        thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth);
        hBox.add(thumbnail, {
          flex: 1
        });
        if (editThumbnailBtn) {
          hBox.add(editThumbnailBtn);
        }
        this._add(hBox);
      }

      const description = this.__createDescription();
      const descriptionLayout = this.__createViewWithEdit(description, this.__openDescriptionEditor);
      this._add(descriptionLayout);

      const tags = this.__createTags();
      const tagsLayout = this.__createViewWithEdit(tags, this.__openTagsEditor);
      if (this.__isOwner()) {
        osparc.utils.Utils.setIdToWidget(tagsLayout.getChildren()[1], "editStudyEditTagsBtn");
      }
      this._add(tagsLayout);

      const classifiers = this.__createClassifiers();
      const classifiersLayout = this.__createViewWithEdit(classifiers, this.__openClassifiersEditor);
      this._add(classifiersLayout);
    },

    __createViewWithEdit: function(view, cb) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      layout.add(view, {
        flex: 1
      });
      if (this.__isOwner()) {
        const editBtn = osparc.utils.Utils.getEditButton();
        editBtn.addListener("execute", () => {
          cb.call(this);
        }, this);
        layout.add(editBtn);
      }

      return layout;
    },

    __extraInfo: function() {
      const grid = new qx.ui.layout.Grid(6, 3);
      grid.setColumnAlign(0, "right", "middle");
      grid.setColumnAlign(1, "left", "middle");
      const moreInfo = new qx.ui.container.Composite(grid).set({
        width: this.self().EXTRA_INFO_WIDTH,
        alignX: "center",
        alignY: "middle"
      });

      const extraInfo = [
        [this.tr("uuid"), this.__createUuid(), null],
        [this.tr("Author"), this.__createOwner(), null],
        [this.tr("Creation date"), this.__createCreationDate(), null],
        [this.tr("Last modified"), this.__createLastChangeDate(), null],
        [this.tr("Access rights"), this.__createAccessRights(), this.__openAccessRights],
        [this.tr("Quality"), this.__createQuality(), this.__openQuality]
      ];
      for (let i=0; i<extraInfo.length; i++) {
        if (extraInfo[i][1]) {
          moreInfo.add(new qx.ui.basic.Label(extraInfo[i][0]).set({
            font: "title-12"
          }), {
            row: i,
            column: 0
          });

          moreInfo.add(extraInfo[i][1], {
            row: i,
            column: 1
          });

          if (extraInfo[i][2]) {
            const editTitleBtn = osparc.utils.Utils.getViewButton();
            editTitleBtn.addListener("execute", () => {
              extraInfo[i][2].call(this);
            }, this);
            moreInfo.add(editTitleBtn, {
              row: i,
              column: 2
            });
          }
        }
      }

      return moreInfo;
    },

    __createTitle: function() {
      const title = osparc.studycard.Utils.createTitle(this.__studyData).set({
        font: "title-16"
      });
      return title;
    },

    __createUuid: function() {
      return osparc.studycard.Utils.createUuid(this.__studyData);
    },

    __createOwner: function() {
      return osparc.studycard.Utils.createOwner(this.__studyData);
    },

    __createCreationDate: function() {
      return osparc.studycard.Utils.createCreationDate(this.__studyData);
    },

    __createLastChangeDate: function() {
      return osparc.studycard.Utils.createLastChangeDate(this.__studyData);
    },

    __createAccessRights: function() {
      return osparc.studycard.Utils.createAccessRights(this.__studyData);
    },

    __createQuality: function() {
      return osparc.studycard.Utils.createQuality(this.__studyData);
    },

    __createThumbnail: function(maxWidth) {
      const maxHeight = 160;
      return osparc.studycard.Utils.createThumbnail(this.__studyData, maxWidth, maxHeight);
    },

    __createDescription: function() {
      const maxHeight = 400;
      return osparc.studycard.Utils.createDescription(this.__studyData, maxHeight);
    },

    __createTags: function() {
      return osparc.studycard.Utils.createTags(this.__studyData);
    },

    __createClassifiers: function() {
      return osparc.studycard.Utils.createClassifiers(this.__studyData);
    },

    __openTitleEditor: function() {
      const title = this.tr("Edit Title");
      const titleEditor = new osparc.component.widget.Renamer(this.__studyData["name"], null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__studyData["name"] = newLabel;
        this.__updateStudy(this.__studyData);
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __openAccessRights: function() {
      const permissionsView = osparc.studycard.Utils.openAccessRights(this.__studyData);
      permissionsView.addListener("updateStudy", e => {
        this.__updateFromCacheAndNotify(this.__studyData["uuid"]);
      }, this);
    },

    __openQuality: function() {
      const qualityEditor = osparc.studycard.Utils.openQuality(this.__studyData);
      [
        "updateStudy",
        "updateTemplate"
      ].forEach(event => {
        qualityEditor.addListener(event, e => {
          this.__updateFromCacheAndNotify(this.__studyData["uuid"]);
        });
      });
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const thubmnailEditor = new osparc.component.widget.Renamer(this.__studyData["thumbnail"], null, title);
      thubmnailEditor.addListener("labelChanged", e => {
        thubmnailEditor.close();
        const dirty = e.getData()["newLabel"];
        const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(dirty);
        if (dirty && dirty !== clean) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was some curation in the text of thumbnail "), "WARNING");
        }
        this.__studyData["thumbnail"] = clean;
        this.__updateStudy(this.__studyData);
      }, this);
      thubmnailEditor.center();
      thubmnailEditor.open();
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const subtitle = this.tr("Supports Markdown");
      const textEditor = new osparc.component.widget.TextEditor(this.__studyData["description"], subtitle, title);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        const newDescription = e.getData();
        this.__studyData["description"] = newDescription;
        this.__updateStudy(this.__studyData);
        win.close();
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __openTagsEditor: function() {
      const tagManager = new osparc.component.form.tag.TagManager(this.__studyData["tags"], null, "study", this.__studyData["uuid"]);
      tagManager.addListener("changeSelected", e => {
        this.__studyData["tags"] = e.getData().selected;
        this.__rebuildLayout();
        this.fireDataEvent("updateTags", this.__studyData["uuid"]);
      }, this);
      tagManager.addListener("close", () => {
        this.fireDataEvent("updateTags", this.__studyData["uuid"]);
      }, this);
    },

    __openClassifiersEditor: function() {
      const classifiersEditor = new osparc.dashboard.ClassifiersEditor(this.__studyData);
      const title = this.tr("Classifiers");
      osparc.ui.window.Window.popUpInWindow(classifiersEditor, title, 400, 400);
      classifiersEditor.addListener("updateResourceClassifiers", () => {
        this.__updateFromCacheAndNotify(this.__studyData["uuid"]);
      }, this);
    },

    __updateStudy: function() {
      const params = {
        url: {
          projectId: this.__studyData["uuid"]
        },
        data: this.__studyData
      };
      osparc.data.Resources.fetch("studies", "put", params)
        .then(studyData => {
          this.fireDataEvent("updateStudy", studyData);
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", studyData);
          this.__setUpdatedData(studyData);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    }
  }
});

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
    this._setLayout(new qx.ui.layout.VBox(8));

    if (studyData && studyData instanceof Object) {
      this.__studyData = osparc.data.model.Study.deepCloneStudyObject(studyData);
    }

    this.addListenerOnce("appear", () => {
      this.__rebuildLayout();
    }, this);
    this.addListener("resize", () => {
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
      const extraInfoLayout = this.__createExtraInfo(extraInfo);


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
      const maxThumbnailHeight = extraInfo.length*20;
      const slim = widgetWidth < this.self().EXTRA_INFO_WIDTH + this.self().THUMBNAIL_MIN_WIDTH + 2*this.self().PADDING - 20;
      if (slim) {
        this._add(extraInfoLayout);
        thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
        const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);
        this._add(thumbnailLayout);
      } else {
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center"
        }));
        hBox.add(extraInfoLayout);
        thumbnailWidth -= this.self().EXTRA_INFO_WIDTH;
        thumbnailWidth = Math.min(thumbnailWidth - 20, this.self().THUMBNAIL_MAX_WIDTH);
        const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
        const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);
        hBox.add(thumbnailLayout, {
          flex: 1
        });
        this._add(hBox);
      }

      if (this.__studyData["description"] || this.__isOwner()) {
        const description = this.__createDescription();
        const descriptionLayout = this.__createViewWithEdit(description, this.__openDescriptionEditor);
        this._add(descriptionLayout);
      }

      if (this.__studyData["tags"].length || this.__isOwner()) {
        const tags = this.__createTags();
        const tagsLayout = this.__createViewWithEdit(tags, this.__openTagsEditor);
        if (this.__isOwner()) {
          osparc.utils.Utils.setIdToWidget(tagsLayout.getChildren()[1], "editStudyEditTagsBtn");
        }
        this._add(tagsLayout);
      }
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
      const extraInfo = [{
        label: this.tr("Author"),
        view: this.__createOwner(),
        action: null
      }, {
        label: this.tr("Creation Date"),
        view: this.__createCreationDate(),
        action: null
      }, {
        label: this.tr("Last Modified"),
        view: this.__createLastChangeDate(),
        action: null
      }, {
        label: this.tr("Access Rights"),
        view: this.__createAccessRights(),
        action: {
          button: osparc.utils.Utils.getViewButton(),
          callback: this.__openAccessRights,
          ctx: this
        }
      }, {
        label: this.tr("Classifiers"),
        view: this.__createClassifiers(),
        action: {
          button: osparc.utils.Utils.getViewButton(),
          callback: this.__openClassifiersEditor,
          ctx: this
        }
      }, {
        label: this.tr("Quality"),
        view: this.__createQuality(),
        action: {
          button: osparc.utils.Utils.getViewButton(),
          callback: this.__openQuality,
          ctx: this
        }
      }];

      if (osparc.data.Permissions.getInstance().isTester()) {
        extraInfo.unshift({
          label: this.tr("UUID"),
          view: this.__createUuid(),
          action: {
            button: osparc.utils.Utils.getCopyButton(),
            callback: this.__copyUuidToClipboard,
            ctx: this
          }
        });
      }
      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.studycard.Utils.createExtraInfo(extraInfo).set({
        width: this.self().EXTRA_INFO_WIDTH
      });

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

    __createClassifiers: function() {
      return osparc.studycard.Utils.createClassifiers(this.__studyData);
    },

    __createQuality: function() {
      return osparc.studycard.Utils.createQuality(this.__studyData);
    },

    __createThumbnail: function(maxWidth, maxHeight = 160) {
      return osparc.studycard.Utils.createThumbnail(this.__studyData, maxWidth, maxHeight);
    },

    __createDescription: function() {
      const maxHeight = 400;
      return osparc.studycard.Utils.createDescription(this.__studyData, maxHeight);
    },

    __createTags: function() {
      return osparc.studycard.Utils.createTags(this.__studyData);
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

    __copyUuidToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.__studyData["uuid"]);
    },

    __openAccessRights: function() {
      const permissionsView = osparc.studycard.Utils.openAccessRights(this.__studyData);
      permissionsView.addListener("updateStudy", e => {
        this.__updateFromCacheAndNotify(this.__studyData["uuid"]);
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

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
    * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
    */
  construct: function(study) {
    this.base(arguments);

    this.set({
      minHeight: 350,
      padding: this.self().PADDING
    });
    this._setLayout(new qx.ui.layout.VBox(8));

    if (study instanceof osparc.data.model.Study) {
      this.setStudy(study);
    } else if (study instanceof Object) {
      const studyModel = new osparc.data.model.Study(study);
      this.setStudy(studyModel);
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

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false
    }
  },

  statics: {
    PADDING: 5,
    EXTRA_INFO_WIDTH: 250,
    THUMBNAIL_MIN_WIDTH: 150,
    THUMBNAIL_MAX_WIDTH: 230
  },

  members: {
    __isOwner: function() {
      return osparc.data.model.Study.isOwner(this.getStudy());
    },

    __rebuildLayout: function() {
      this._removeAll();

      const title = this.__createTitle();
      const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
      this._add(titleLayout);

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);


      const bounds = this.getBounds();
      const offset = 30;
      let widgetWidth = bounds ? bounds.width - offset : 500 - offset;
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

      if (this.getStudy().getDescription() || this.__isOwner()) {
        const description = this.__createDescription();
        const descriptionLayout = this.__createViewWithEdit(description, this.__openDescriptionEditor);
        this._add(descriptionLayout);
      }

      if (this.getStudy().getTags().length || this.__isOwner()) {
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
        action: (this.getStudy().getClassifiers().length || this.__isOwner()) ? {
          button: osparc.utils.Utils.getViewButton(),
          callback: this.__openClassifiers,
          ctx: this
        } : null
      }];

      if (this.getStudy().getQuality() && osparc.component.metadata.Quality.isEnabled(this.getStudy().getQuality())) {
        extraInfo.push({
          label: this.tr("Quality"),
          view: this.__createQuality(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.__openQuality,
            ctx: this
          }
        });
      }

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
      const title = osparc.studycard.Utils.createTitle(this.getStudy()).set({
        font: "title-16"
      });
      return title;
    },

    __createUuid: function() {
      return osparc.studycard.Utils.createUuid(this.getStudy());
    },

    __createOwner: function() {
      return osparc.studycard.Utils.createOwner(this.getStudy());
    },

    __createCreationDate: function() {
      return osparc.studycard.Utils.createCreationDate(this.getStudy());
    },

    __createLastChangeDate: function() {
      return osparc.studycard.Utils.createLastChangeDate(this.getStudy());
    },

    __createAccessRights: function() {
      return osparc.studycard.Utils.createAccessRights(this.getStudy());
    },

    __createClassifiers: function() {
      return osparc.studycard.Utils.createClassifiers(this.getStudy());
    },

    __createQuality: function() {
      return osparc.studycard.Utils.createQuality(this.getStudy());
    },

    __createThumbnail: function(maxWidth, maxHeight = 160) {
      return osparc.studycard.Utils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
    },

    __createDescription: function() {
      const maxHeight = 400;
      return osparc.studycard.Utils.createDescription(this.getStudy(), maxHeight);
    },

    __createTags: function() {
      return osparc.studycard.Utils.createTags(this.getStudy());
    },

    __openTitleEditor: function() {
      const title = this.tr("Edit Title");
      const titleEditor = new osparc.component.widget.Renamer(this.getStudy().getName(), null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__updateStudy({
          "name": newLabel
        });
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __copyUuidToClipboard: function() {
      osparc.utils.Utils.copyTextToClipboard(this.getStudy().getUuid());
    },

    __openAccessRights: function() {
      const permissionsView = osparc.studycard.Utils.openAccessRights(this.getStudy().serialize());
      permissionsView.addListener("updateStudy", e => {
        const updatedData = e.getData();
        this.getStudy().setAccessRights(updatedData["accessRights"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },

    __openClassifiers: function() {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (this.__isOwner()) {
        classifiers = new osparc.component.metadata.ClassifiersEditor(this.getStudy().serialize());
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedData = e.getData();
          this.getStudy().setClassifiers(updatedData["classifiers"]);
          this.fireDataEvent("updateStudy", updatedData);
        }, this);
      } else {
        classifiers = new osparc.component.metadata.ClassifiersViewer(this.getStudy().serialize());
        osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
      }
    },

    __openQuality: function() {
      const qualityEditor = osparc.studycard.Utils.openQuality(this.getStudy().serialize());
      qualityEditor.addListener("updateQuality", e => {
        const updatedData = e.getData();
        this.getStudy().setQuality(updatedData["quality"]);
        this.fireDataEvent("updateStudy", updatedData);
      });
    },

    __openTagsEditor: function() {
      const tagManager = new osparc.component.form.tag.TagManager(this.getStudy().serialize(), null, "study", this.getStudy().getUuid()).set({
        liveUpdate: false
      });
      tagManager.addListener("updateTags", e => {
        tagManager.close();
        const updatedData = e.getData();
        this.getStudy().setTags(updatedData["tags"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const thubmnailEditor = new osparc.component.widget.Renamer(this.getStudy().getThumbnail(), null, title);
      thubmnailEditor.addListener("labelChanged", e => {
        thubmnailEditor.close();
        const dirty = e.getData()["newLabel"];
        const clean = osparc.wrapper.DOMPurify.getInstance().sanitize(dirty);
        if (dirty && dirty !== clean) {
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was some curation in the text of thumbnail "), "WARNING");
        }
        this.__updateStudy({
          "thumbnail": clean
        });
      }, this);
      thubmnailEditor.center();
      thubmnailEditor.open();
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const subtitle = this.tr("Supports Markdown");
      const textEditor = new osparc.component.widget.TextEditor(this.getStudy().getDescription(), subtitle, title);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__updateStudy({
          "description": newDescription
        });
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __updateStudy: function(params) {
      this.getStudy().updateStudy(params)
        .then(studyData => {
          this.fireDataEvent("updateStudy", studyData);
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", studyData);
        })
        .catch(err => {
          console.error(err);
          osparc.component.message.FlashMessenger.getInstance().logAs(this.tr("There was an error while updating the information."), "ERROR");
        });
    }
  }
});

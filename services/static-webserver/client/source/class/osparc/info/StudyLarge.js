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


qx.Class.define("osparc.info.StudyLarge", {
  extend: osparc.info.CardLarge,

  /**
    * @param study {osparc.data.model.Study|Object} Study or Serialized Study Object
    * @param openOptions {Boolean} open edit options in new window or fire event
    */
  construct: function(study, openOptions = true) {
    this.base(arguments);

    if (study instanceof osparc.data.model.Study) {
      this.setStudy(study);
    } else if (study instanceof Object) {
      const studyModel = new osparc.data.model.Study(study);
      this.setStudy(studyModel);
    }

    if (openOptions !== undefined) {
      this.setOpenOptions(openOptions);
    }

    this._attachHandlers();
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

  members: {
    __canIWrite: function() {
      return osparc.data.model.Study.canIWrite(this.getStudy().getAccessRights());
    },

    _rebuildLayout: function() {
      this._removeAll();

      const title = this.__createTitle();
      const titleLayout = this.__createViewWithEdit(title, this.__openTitleEditor);
      this._add(titleLayout);

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);


      const bounds = this.getBounds();
      const offset = 30;
      let widgetWidth = bounds ? bounds.width - offset : 500 - offset;
      let thumbnailWidth = widgetWidth - 2 * osparc.info.CardLarge.PADDING;
      const maxThumbnailHeight = extraInfo.length*20;
      const slim = widgetWidth < osparc.info.CardLarge.EXTRA_INFO_WIDTH + osparc.info.CardLarge.THUMBNAIL_MIN_WIDTH + 2 * osparc.info.CardLarge.PADDING - 20;
      let hBox = null;
      if (slim) {
        this._add(extraInfoLayout);
      } else {
        hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(3).set({
          alignX: "center"
        }));
        hBox.add(extraInfoLayout);
        thumbnailWidth -= osparc.info.CardLarge.EXTRA_INFO_WIDTH;
      }
      thumbnailWidth = Math.min(thumbnailWidth - 20, osparc.info.CardLarge.THUMBNAIL_MAX_WIDTH);
      const thumbnail = this.__createThumbnail(thumbnailWidth, maxThumbnailHeight);
      const thumbnailLayout = this.__createViewWithEdit(thumbnail, this.__openThumbnailEditor);
      thumbnailLayout.getLayout().set({
        alignX: "center"
      });
      if (slim) {
        this._add(thumbnailLayout);
      } else {
        hBox.add(thumbnailLayout, {
          flex: 1
        });
        this._add(hBox);
      }

      if (osparc.product.Utils.showDisableServiceAutoStart() && this.__canIWrite()) {
        const autoStart = this.__createDisableServiceAutoStart();
        this._add(autoStart);
      }

      if (this.getStudy().getTags().length || this.__canIWrite()) {
        const tags = this.__createTags();
        const editInTitle = this.__createViewWithEdit(tags.getChildren()[0], null);
        tags.addAt(editInTitle, 0);
        if (this.__canIWrite()) {
          const editButton = editInTitle.getChildren()[1];
          editButton.setIcon("@FontAwesome5Solid/eye/12");
          editButton.addListener("execute", () => this.fireEvent("openTags"), this);
          osparc.utils.Utils.setIdToWidget(editButton, "editStudyEditTagsBtn");
        }
        this._add(tags);
      }

      if (this.getStudy().getDescription() || this.__canIWrite()) {
        const description = this.__createDescription();
        const editInTitle = this.__createViewWithEdit(description.getChildren()[0], this.__openDescriptionEditor);
        description.addAt(editInTitle, 0);
        this._add(description);
      }
    },

    __createViewWithEdit: function(view, cb) {
      const layout = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
        alignY: "middle"
      }));
      layout.add(view);
      if (this.__canIWrite()) {
        const editBtn = osparc.utils.Utils.getEditButton();
        if (cb) {
          editBtn.addListener("execute", () => cb.call(this), this);
        }
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
          callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
          ctx: this
        }
      }];

      if (
        osparc.product.Utils.showQuality() &&
        this.getStudy().getQuality() &&
        osparc.component.metadata.Quality.isEnabled(this.getStudy().getQuality())
      ) {
        extraInfo.push({
          label: this.tr("Quality"),
          view: this.__createQuality(),
          action: {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.isOpenOptions() ? this.__openQuality : "openQuality",
            ctx: this
          }
        });
      }

      if (osparc.product.Utils.showClassifiers()) {
        extraInfo.push({
          label: this.tr("Classifiers"),
          view: this.__createClassifiers(),
          action: (this.getStudy().getClassifiers().length || this.__canIWrite()) ? {
            button: osparc.utils.Utils.getViewButton(),
            callback: this.isOpenOptions() ? this.__openClassifiers : "openClassifiers",
            ctx: this
          } : null
        });
      }

      extraInfo.splice(0, 0, {
        label: osparc.utils.Utils.capitalize(osparc.product.Utils.getStudyAlias()) + " ID",
        view: this.__createStudyId(),
        action: {
          button: osparc.utils.Utils.getCopyButton(),
          callback: this.__copyUuidToClipboard,
          ctx: this
        }
      });

      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      const moreInfo = osparc.info.StudyUtils.createExtraInfo(extraInfo).set({
        width: osparc.info.CardLarge.EXTRA_INFO_WIDTH
      });

      return moreInfo;
    },

    __createTitle: function() {
      const title = osparc.info.StudyUtils.createTitle(this.getStudy()).set({
        font: "text-14"
      });
      return title;
    },

    __createStudyId: function() {
      return osparc.info.StudyUtils.createUuid(this.getStudy());
    },

    __createOwner: function() {
      return osparc.info.StudyUtils.createOwner(this.getStudy());
    },

    __createCreationDate: function() {
      return osparc.info.StudyUtils.createCreationDate(this.getStudy());
    },

    __createLastChangeDate: function() {
      return osparc.info.StudyUtils.createLastChangeDate(this.getStudy());
    },

    __createAccessRights: function() {
      return osparc.info.StudyUtils.createAccessRights(this.getStudy());
    },

    __createClassifiers: function() {
      return osparc.info.StudyUtils.createClassifiers(this.getStudy());
    },

    __createQuality: function() {
      return osparc.info.StudyUtils.createQuality(this.getStudy());
    },

    __createThumbnail: function(maxWidth, maxHeight = 160) {
      return osparc.info.StudyUtils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
    },

    __createDisableServiceAutoStart: function() {
      return osparc.info.StudyUtils.createDisableServiceAutoStart(this.getStudy());
    },

    __createTags: function() {
      return osparc.info.StudyUtils.createTags(this.getStudy());
    },

    __createDescription: function() {
      const maxHeight = 400;
      return osparc.info.StudyUtils.createDescription(this.getStudy(), maxHeight);
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
      const permissionsView = osparc.info.StudyUtils.openAccessRights(this.getStudy().serialize());
      permissionsView.addListener("updateStudy", e => {
        const updatedData = e.getData();
        this.getStudy().setAccessRights(updatedData["accessRights"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },

    __openClassifiers: function() {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (this.__canIWrite()) {
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
      const qualityEditor = osparc.info.StudyUtils.openQuality(this.getStudy().serialize());
      qualityEditor.addListener("updateQuality", e => {
        const updatedData = e.getData();
        this.getStudy().setQuality(updatedData["quality"]);
        this.fireDataEvent("updateStudy", updatedData);
      });
    },

    __openTagsEditor: function() {
      const tagManager = new osparc.component.form.tag.TagManager(this.getStudy().serialize());
      const win = osparc.component.form.tag.TagManager.popUpInWindow(tagManager);
      tagManager.addListener("updateTags", e => {
        win.close();
        const updatedData = e.getData();
        this.getStudy().setTags(updatedData["tags"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },

    __openThumbnailEditor: function() {
      const title = this.tr("Edit Thumbnail");
      const oldThumbnail = this.getStudy().getThumbnail();
      let suggestions = new Set([]);
      const wb = this.getStudy().getWorkbench();
      const nodes = wb.getWorkbenchInitData() ? wb.getWorkbenchInitData() : wb.getNodes();
      Object.values(nodes).forEach(node => {
        const srvMetadata = osparc.utils.Services.getMetaData(node["key"], node["version"]);
        if (srvMetadata && srvMetadata["thumbnail"] && !osparc.data.model.Node.isFrontend(node)) {
          suggestions.add(srvMetadata["thumbnail"]);
        }
      });
      suggestions = Array.from(suggestions);
      const thumbnailEditor = new osparc.component.editor.ThumbnailEditor(oldThumbnail, suggestions);
      const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, suggestions.length > 2 ? 500 : 350, suggestions.length ? 280 : 115);
      thumbnailEditor.addListener("updateThumbnail", e => {
        win.close();
        const validUrl = e.getData();
        this.__updateStudy({
          "thumbnail": validUrl
        });
      }, this);
      thumbnailEditor.addListener("cancel", () => win.close());
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.component.editor.TextEditor(this.getStudy().getDescription());
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

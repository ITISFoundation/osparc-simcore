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
    * @param study {osparc.data.model.Study} Study model
    * @param openOptions {Boolean} open edit options in new window or fire event
    */
  construct: function(study, openOptions = true) {
    this.base(arguments);

    this.setStudy(study);
    if ("resourceType" in study) {
      this.__isTemplate = study["resourceType"] === "template";
    }

    if (openOptions !== undefined) {
      this.setOpenOptions(openOptions);
    }

    this._attachHandlers();
  },

  events: {
    "updateStudy": "qx.event.type.Data"
  },

  properties: {
    study: {
      check: "osparc.data.model.Study",
      init: null,
      nullable: false
    }
  },

  members: {
    __isTemplate: null,

    __canIWrite: function() {
      return osparc.data.model.Study.canIWrite(this.getStudy().getAccessRights());
    },

    _rebuildLayout: function() {
      this._removeAll();

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const mainHBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));

      const leftVBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(5));
      mainHBox.add(leftVBox, {
        flex: 1
      });

      vBox.add(mainHBox);

      const extraInfo = this.__extraInfo();
      const extraInfoLayout = this.__createExtraInfo(extraInfo);

      leftVBox.add(extraInfoLayout);

      let text = osparc.product.Utils.getStudyAlias({firstUpperCase: true}) + " Id";
      if (this.__isTemplate) {
        text = osparc.product.Utils.getTemplateAlias({firstUpperCase: true}) + " Id";
      }
      const copyIdButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/copy/12").set({
        label: text,
        toolTipText: "Copy " + text,
        marginTop: 15,
        allowGrowX: false
      });
      copyIdButton.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(this.getStudy().getUuid()));
      leftVBox.add(copyIdButton);

      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(vBox);

      this._add(scrollContainer, {
        flex: 1
      });
    },

    __extraInfo: function() {
      const extraInfo = {
        "TITLE": {
          label: this.tr("Title:"),
          view: osparc.info.StudyUtils.createTitle(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getEditButton(this.__canIWrite()),
            callback: this.__canIWrite() ? this.__openTitleEditor : null,
            ctx: this
          }
        },
        "THUMBNAIL": {
          label: this.tr("Thumbnail:"),
          view: this.__createThumbnail(),
          action: {
            button: osparc.utils.Utils.getEditButton(this.__canIWrite()),
            callback: this.__canIWrite() ? this.__openThumbnailEditor : null,
            ctx: this
          }
        },
        "DESCRIPTION": {
          label: this.tr("Description:"),
          view: osparc.info.StudyUtils.createDescriptionMD(this.getStudy(), 150),
          action: {
            button: osparc.utils.Utils.getEditButton(this.__canIWrite()),
            callback: this.__canIWrite() ? this.__openDescriptionEditor : null,
            ctx: this
          }
        },
        "AUTHOR": {
          label: this.tr("Author:"),
          view: osparc.info.StudyUtils.createOwner(this.getStudy()),
          action: null
        },
        "ACCESS_RIGHTS": {
          label: this.tr("Access:"),
          view: osparc.info.StudyUtils.createAccessRights(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getLinkButton(this.__canIWrite()),
            callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
            ctx: this
          }
        },
        "CREATED": {
          label: this.tr("Created:"),
          view: osparc.info.StudyUtils.createCreationDate(this.getStudy()),
          action: null
        },
        "MODIFIED": {
          label: this.tr("Modified:"),
          view: osparc.info.StudyUtils.createLastChangeDate(this.getStudy()),
          action: null
        },
        "TAGS": {
          label: this.tr("Tags:"),
          view: osparc.info.StudyUtils.createTags(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getLinkButton(this.__canIWrite()),
            callback: this.isOpenOptions() ? this.__openTagsEditor : "openTags",
            ctx: this
          }
        }
      };

      if (
        osparc.product.Utils.showQuality() &&
        this.getStudy().getQuality() &&
        osparc.metadata.Quality.isEnabled(this.getStudy().getQuality())
      ) {
        extraInfo["QUALITY"] = {
          label: this.tr("Quality:"),
          view: osparc.info.StudyUtils.createQuality(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getLinkButton(),
            callback: this.isOpenOptions() ? this.__openQuality : "openQuality",
            ctx: this
          }
        };
      }

      if (osparc.product.Utils.showClassifiers()) {
        extraInfo["CLASSIFIERS"] = {
          label: this.tr("Classifiers:"),
          view: osparc.info.StudyUtils.createClassifiers(this.getStudy()),
          action: (this.getStudy().getClassifiers().length || this.__canIWrite()) ? {
            button: osparc.utils.Utils.getLinkButton(),
            callback: this.isOpenOptions() ? this.__openClassifiers : "openClassifiers",
            ctx: this
          } : null
        };
      }

      return extraInfo;
    },

    __createExtraInfo: function(extraInfo) {
      return osparc.info.StudyUtils.createExtraInfoGrid(extraInfo);
    },

    __createStudyId: function() {
      return osparc.info.StudyUtils.createUuid(this.getStudy());
    },

    __createThumbnail: function(maxWidth = 190, maxHeight = 220) {
      const thumb = osparc.info.StudyUtils.createThumbnail(this.getStudy(), maxWidth, maxHeight);
      thumb.set({
        maxWidth: 120,
        maxHeight: 139
      });
      thumb.getChildControl("image").set({
        width: 120,
        height: 139,
        scale: true,
      });

      return thumb;
    },

    __openTitleEditor: function() {
      const title = this.tr("Edit Title");
      const titleEditor = new osparc.widget.Renamer(this.getStudy().getName(), null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__patchStudy("name", newLabel);
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __openAccessRights: function() {
      const studyData = this.getStudy().serialize();
      studyData["resourceType"] = this.__isTemplate ? "template" : "study";
      const permissionsView = osparc.info.StudyUtils.openAccessRights(studyData);
      permissionsView.addListener("updateAccessRights", e => {
        const updatedData = e.getData();
        this.getStudy().setAccessRights(updatedData["accessRights"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },

    __openClassifiers: function() {
      const title = this.tr("Classifiers");
      let classifiers = null;
      if (this.__canIWrite()) {
        classifiers = new osparc.metadata.ClassifiersEditor(this.getStudy().serialize());
        const win = osparc.ui.window.Window.popUpInWindow(classifiers, title, 400, 400);
        classifiers.addListener("updateClassifiers", e => {
          win.close();
          const updatedData = e.getData();
          this.getStudy().setClassifiers(updatedData["classifiers"]);
          this.fireDataEvent("updateStudy", updatedData);
        }, this);
      } else {
        classifiers = new osparc.metadata.ClassifiersViewer(this.getStudy().serialize());
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
      const tagManager = new osparc.form.tag.TagManager(this.getStudy().serialize());
      const win = osparc.form.tag.TagManager.popUpInWindow(tagManager);
      tagManager.addListener("updateTags", e => {
        win.close();
        const updatedData = e.getData();
        this.getStudy().setTags(updatedData["tags"]);
        this.fireDataEvent("updateStudy", updatedData);
      }, this);
    },

    __openThumbnailEditor: function() {
      osparc.editor.ThumbnailSuggestions.extractThumbnailSuggestions(this.getStudy())
        .then(suggestions => {
          const title = this.tr("Edit Thumbnail");
          const oldThumbnail = this.getStudy().getThumbnail();
          const thumbnailEditor = new osparc.editor.ThumbnailEditor(oldThumbnail, suggestions);
          const win = osparc.ui.window.Window.popUpInWindow(thumbnailEditor, title, suggestions.length > 2 ? 500 : 350, suggestions.length ? 280 : 115);
          thumbnailEditor.addListener("updateThumbnail", e => {
            win.close();
            const validUrl = e.getData();
            this.__patchStudy("thumbnail", validUrl);
          }, this);
          thumbnailEditor.addListener("cancel", () => win.close());
        })
        .catch(err => console.error(err));
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.editor.MarkdownEditor(this.getStudy().getDescription());
      textEditor.setMaxHeight(570);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__patchStudy("description", newDescription);
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __patchStudy: function(fieldKey, value) {
      this.getStudy().patchStudy({[fieldKey]: value})
        .then(studyData => {
          studyData["resourceType"] = this.__isTemplate ? "template" : "study";
          this.fireDataEvent("updateStudy", studyData);
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", studyData);
        })
        .catch(err => {
          console.error(err);
          const msg = err.message || this.tr("There was an error while updating the information.");
          osparc.FlashMessenger.getInstance().logAs(msg, "ERROR");
        });
    }
  }
});

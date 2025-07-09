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
    __canIWrite: function() {
      return osparc.data.model.Study.canIWrite(this.getStudy().getAccessRights());
    },

    _rebuildLayout: function() {
      this._removeAll();

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      if (
        this.__canIWrite() &&
        this.getStudy().getTemplateType() &&
        osparc.data.Permissions.getInstance().isTester()
      ) {
        // let testers change the template type
        const hBox = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
          alignY: "middle",
        }));
        hBox.add(new qx.ui.basic.Label(this.tr("Template Type:")));
        const templateTypeSB = osparc.study.Utils.createTemplateTypeSB();
        hBox.add(templateTypeSB);
        const saveBtn = new osparc.ui.form.FetchButton(this.tr("Save")).set({
          enabled: false,
          allowGrowX: false,
        });
        hBox.add(saveBtn);
        vBox.add(hBox);

        templateTypeSB.addListener("changeSelection", e => {
          const selected = e.getData()[0];
          if (selected) {
            const templateType = selected.getModel();
            saveBtn.setEnabled(this.getStudy().getTemplateType() !== templateType);
          }
        }, this);

        templateTypeSB.getSelectables().forEach(selectable => {
          if (selectable.getModel() === this.getStudy().getTemplateType()) {
            templateTypeSB.setSelection([selectable]);
          }
        });

        saveBtn.addListener("execute", () => {
          const selected = templateTypeSB.getSelection()[0];
          if (selected) {
            saveBtn.setFetching(true);
            const templateType = selected.getModel();
            osparc.store.Study.getInstance().patchTemplateType(this.getStudy().getUuid(), templateType)
              .then(() => osparc.FlashMessenger.logAs(this.tr("Template type updated, please reload"), "INFO"))
              .finally(() => saveBtn.setFetching(false));
          }
        }, this);
      }

      const infoElements = this.__infoElements();
      const isStudy = true;
      const infoLayout = osparc.info.Utils.infoElementsToLayout(infoElements, isStudy);
      vBox.add(infoLayout);

      // Copy Id button
      let text = osparc.product.Utils.getStudyAlias({firstUpperCase: true}) + " Id";
      if (this.getStudy().getTemplateType()) {
        text = osparc.product.Utils.getTemplateAlias({firstUpperCase: true}) + " Id";
      }
      const copyIdButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/copy/12").set({
        label: text,
        toolTipText: "Copy " + text,
        marginTop: 15,
        allowGrowX: false
      });
      copyIdButton.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(this.getStudy().getUuid()));
      vBox.add(copyIdButton);

      // All in a scroll container
      const scrollContainer = new qx.ui.container.Scroll();
      scrollContainer.add(vBox);

      this._add(scrollContainer, {
        flex: 1
      });
    },

    __infoElements: function() {
      const canIWrite = this.__canIWrite();

      const infoLayout = {
        "TITLE": {
          view: osparc.info.StudyUtils.createTitle(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openTitleEditor : null,
            ctx: this
          }
        },
        "THUMBNAIL": {
          view: this.__createThumbnail(),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openThumbnailEditor : null,
            ctx: this
          }
        },
        "DESCRIPTION": {
          view: osparc.info.StudyUtils.createDescription(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openDescriptionEditor : null,
            ctx: this
          }
        },
        "AUTHOR": {
          label: this.tr("Author"),
          view: osparc.info.StudyUtils.createOwner(this.getStudy()),
          action: null
        },
        "ACCESS_RIGHTS": {
          label: this.tr("Access"),
          view: osparc.info.StudyUtils.createAccessRights(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getLinkButton(canIWrite),
            callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
            ctx: this
          }
        },
        "CREATED": {
          label: this.tr("Created"),
          view: osparc.info.StudyUtils.createCreationDate(this.getStudy()),
          action: null
        },
        "MODIFIED": {
          label: this.tr("Modified"),
          view: osparc.info.StudyUtils.createLastChangeDate(this.getStudy()),
          action: null
        },
        "TAGS": {
          label: this.tr("Tags"),
          view: osparc.info.StudyUtils.createTags(this.getStudy()),
          action: {
            button: osparc.utils.Utils.getLinkButton(canIWrite),
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
        infoLayout["QUALITY"] = {
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
        infoLayout["CLASSIFIERS"] = {
          label: this.tr("Classifiers:"),
          view: osparc.info.StudyUtils.createClassifiers(this.getStudy()),
          action: (this.getStudy().getClassifiers().length || canIWrite) ? {
            button: osparc.utils.Utils.getLinkButton(),
            callback: this.isOpenOptions() ? this.__openClassifiers : "openClassifiers",
            ctx: this
          } : null
        };
      }

      if (this.getStudy().getTemplateType() === null) {
        // studies only
        const pathLabel = new qx.ui.basic.Label();
        pathLabel.setValue(this.getStudy().getLocationString());
        infoLayout["LOCATION"] = {
          label: this.tr("Location:"),
          view: pathLabel,
          action: null
        };
      }

      return infoLayout;
    },

    __createStudyId: function() {
      return osparc.info.StudyUtils.createUuid(this.getStudy());
    },

    __createThumbnail: function() {
      const maxWidth = 190;
      const maxHeight = 220;
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
      studyData["resourceType"] = this.getStudy().getTemplateType() ? "template" : "study";
      const collaboratorsView = osparc.info.StudyUtils.openAccessRights(studyData);
      collaboratorsView.addListener("updateAccessRights", e => {
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
          studyData["resourceType"] = this.getStudy().getTemplateType() ? "template" : "study";
          this.fireDataEvent("updateStudy", studyData);
          qx.event.message.Bus.getInstance().dispatchByName("updateStudy", studyData);
        })
        .catch(err => {
          const msg = this.tr("An issue occurred while updating the information.");
          osparc.FlashMessenger.logError(err, msg);
        });
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.info.FunctionLarge", {
  extend: osparc.info.CardLarge,

  /**
    * @param func {osparc.data.model.Function} Function model
    */
  construct: function(func) {
    this.base(arguments);

    this.setFunction(func);

    this.setOpenOptions(false);

    this._attachHandlers();
  },

  events: {
    "updateFunction": "qx.event.type.Data",
  },

  properties: {
    function: {
      check: "osparc.data.model.Function",
      init: null,
      nullable: false
    }
  },

  members: {
    __canIWrite: function() {
      // return osparc.data.model.Function.canIWrite(this.getFunction().getAccessRights());
      return true;
    },

    _rebuildLayout: function() {
      this._removeAll();

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const infoElements = this.__infoElements();
      const isStudy = true;
      const infoLayout = osparc.info.Utils.infoElementsToLayout(infoElements, isStudy);
      vBox.add(infoLayout);

      // Copy Id button
      const text = "Function Id";
      const copyIdButton = new qx.ui.form.Button(null, "@FontAwesome5Solid/copy/12").set({
        label: text,
        toolTipText: "Copy " + text,
        marginTop: 15,
        allowGrowX: false
      });
      copyIdButton.addListener("execute", () => osparc.utils.Utils.copyTextToClipboard(this.getFunction().getUuid()));
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
          view: osparc.info.StudyUtils.createTitle(this.getFunction()),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openTitleEditor : null,
            ctx: this
          }
        },
        "THUMBNAIL": {
          view: this.__createThumbnail(),
          action: null
        },
        "DESCRIPTION": {
          view: osparc.info.StudyUtils.createDescription(this.getFunction()),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openDescriptionEditor : null,
            ctx: this
          }
        },
        /*
        "AUTHOR": {
          label: this.tr("Author"),
          view: osparc.info.StudyUtils.createOwner(this.getFunction()),
          action: null
        },
        */
        "ACCESS_RIGHTS": {
          label: this.tr("Access"),
          view: osparc.info.StudyUtils.createAccessRights(this.getFunction()),
          action: {
            button: osparc.utils.Utils.getLinkButton(canIWrite),
            callback: this.isOpenOptions() ? this.__openAccessRights : "openAccessRights",
            ctx: this
          }
        },
        "CREATED": {
          label: this.tr("Created"),
          view: osparc.info.StudyUtils.createCreationDate(this.getFunction()),
          action: null
        },
        "MODIFIED": {
          label: this.tr("Modified"),
          view: osparc.info.StudyUtils.createLastChangeDate(this.getFunction()),
          action: null
        },
      };
      return infoLayout;
    },

    __createThumbnail: function() {
      const maxWidth = 190;
      const maxHeight = 220;
      const thumb = osparc.info.StudyUtils.createThumbnail(this.getFunction(), maxWidth, maxHeight);
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
      const titleEditor = new osparc.widget.Renamer(this.getFunction().getName(), null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__patchFunction("name", newLabel);
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.editor.MarkdownEditor(this.getStudy().getDescription());
      textEditor.setMaxHeight(570);
      const win = osparc.ui.window.Window.popUpInWindow(textEditor, title, 400, 300);
      textEditor.addListener("textChanged", e => {
        win.close();
        const newDescription = e.getData();
        this.__patchFunction("description", newDescription);
      }, this);
      textEditor.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __patchFunction: function(fieldKey, value) {
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

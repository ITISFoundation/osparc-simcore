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
    _rebuildLayout: function() {
      this._removeAll();

      const vBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));

      const infoElements = this.__infoElements();
      const isStudy = true;
      const infoLayout = osparc.info.Utils.infoElementsToLayout(infoElements, isStudy);
      vBox.add(infoLayout);

      // inputs, default inputs and outputs
      const info = {
        "Inputs": this.getFunction().getInputSchema()["schema_content"],
        "Default Inputs": this.getFunction().getDefaultInputs(),
        "Outputs": this.getFunction().getOutputSchema()["schema_content"],
      };
      const divId = "function-info-viewer";
      const htmlEmbed = osparc.wrapper.JsonFormatter.getInstance().createContainer(divId);
      vBox.add(htmlEmbed, {
        flex: 1
      });
      vBox.addListener("appear", () => {
        osparc.wrapper.JsonFormatter.getInstance().setJson(info, divId);
      });

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
      const canIWrite = this.getFunction().canIWrite();

      const infoLayout = {
        "TITLE": {
          view: osparc.info.FunctionUtils.createTitle(this.getFunction()),
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
          view: osparc.info.FunctionUtils.createDescription(this.getFunction()),
          action: {
            button: osparc.utils.Utils.getEditButton(canIWrite),
            callback: canIWrite ? this.__openDescriptionEditor : null,
            ctx: this
          }
        },
        "ACCESS_RIGHTS": {
          label: this.tr("Permissions"),
          view: osparc.info.FunctionUtils.createOwner(this.getFunction()),
          action: null
        },
        "CREATED": {
          label: this.tr("Created"),
          view: osparc.info.FunctionUtils.createCreationDate(this.getFunction()),
          action: null
        },
        "MODIFIED": {
          label: this.tr("Modified"),
          view: osparc.info.FunctionUtils.createLastChangeDate(this.getFunction()),
          action: null
        },
      };
      return infoLayout;
    },

    __createThumbnail: function() {
      const maxWidth = 190;
      const maxHeight = 220;
      const thumb = osparc.info.FunctionUtils.createThumbnail(this.getFunction(), maxWidth, maxHeight);
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
      const titleEditor = new osparc.widget.Renamer(this.getFunction().getTitle(), null, title);
      titleEditor.addListener("labelChanged", e => {
        titleEditor.close();
        const newLabel = e.getData()["newLabel"];
        this.__patchFunction("title", newLabel);
      }, this);
      titleEditor.center();
      titleEditor.open();
    },

    __openDescriptionEditor: function() {
      const title = this.tr("Edit Description");
      const textEditor = new osparc.editor.MarkdownEditor(this.getFunction().getDescription());
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
      this.getFunction().patchFunction({[fieldKey]: value})
        .then(functionData => {
          this.fireDataEvent("updateFunction", functionData);
          qx.event.message.Bus.getInstance().dispatchByName("updateFunction", functionData);
        })
        .catch(err => osparc.FlashMessenger.logError(err));
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *   Window that shows a text field with the input item label
 * that can be used for renaming it
 *
 * *Example*
 *
 * Here is a little example of how to use the widget.
 *
 * <pre class='javascript'>
 *   let itemRenamer = new osparc.widget.Renamer(selectedItem.getLabel());
 *   itemRenamer.addListener("labelChanged", e => {
 *     const data = e.getData();
 *     const newLabel = data.newLabel;
 *     selectedItem.setLabel(newLabel);
 *   }, this);
 *   itemRenamer.open();
 * </pre>
 */

qx.Class.define("osparc.widget.Renamer", {
  extend: osparc.ui.window.Window,

  construct: function(oldLabel = "", subtitle = "", winTitle) {
    this.base(arguments, winTitle || this.tr("Rename"));

    const maxWidth = 400;
    const minWidth = 250;
    const labelWidth = oldLabel ? Math.min(Math.max(parseInt(oldLabel.length*4), minWidth), maxWidth) : minWidth;
    this.set({
      layout: new qx.ui.layout.VBox(5),
      autoDestroy: true,
      padding: 2,
      modal: true,
      showMaximize: false,
      showMinimize: false,
      width: labelWidth,
      clickAwayClose: true
    });

    this.__populateNodeLabelEditor(oldLabel, labelWidth);
    this.__addSubtitle(subtitle);
    this.__attachEventHandlers();
  },

  events: {
    "labelChanged": "qx.event.type.Data"
  },

  properties: {
    maxChars: {
      check: "Number",
      init: 50,
      apply: "__applyMaxChars",
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "main-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));
          this.add(control);
          break;
        case "text-field":
          control = new qx.ui.form.TextField().set({
            placeholder: this.tr("Type text"),
            allowGrowX: true
          });
          this.getChildControl("main-layout").add(control, {
            flex: 1
          });
          break;
        case "save-button":
          control = new qx.ui.form.Button(this.tr("Save")).set({
            appearance: "form-button",
            padding: [1, 5]
          });
          this.getChildControl("main-layout").add(control);
          break;
        case "subtitle":
          control = new qx.ui.basic.Label().set({
            font: "text-12"
          });
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __populateNodeLabelEditor: function(oldLabel, labelWidth) {
      const textField = this.getChildControl("text-field").set({
        value: oldLabel,
        minWidth: labelWidth,
      });

      const saveButton = this.getChildControl("save-button");
      saveButton.addListener("execute", () => {
        const newLabel = textField.getValue();
        const data = {
          newLabel
        };
        this.fireDataEvent("labelChanged", data);
      }, this);

      this.addListener("appear", () => {
        textField.focus();
        if (textField.getValue()) {
          textField.setTextSelection(0, textField.getValue().length);
        }
      }, this);
    },

    __applyMaxChars: function(value) {
      this.getChildControl("text-field").setMaxLength(value);

      this.__addSubtitle(this.tr("%1 characters max", value));
    },

    __addSubtitle: function(subtitleText) {
      if (subtitleText) {
        this.getChildControl("subtitle").setValue(subtitleText);
      }
    },

    __attachEventHandlers: function() {
      let command = new qx.ui.command.Command("Enter");
      command.addListener("execute", () => {
        this.getChildControl("save-button").execute();
        command.dispose();
        command = null;
      });

      let commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", () => {
        this.close();
        commandEsc.dispose();
        commandEsc = null;
      });
    }
  }
});

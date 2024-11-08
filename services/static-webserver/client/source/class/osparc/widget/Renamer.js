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

    const maxWidth = 350;
    const minWidth = 150;
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

  members: {
    __save: null,

    __populateNodeLabelEditor: function(oldLabel, labelWidth) {
      const nodeLabelEditor = new qx.ui.container.Composite(new qx.ui.layout.HBox(10));

      // Create a text field in which to edit the data
      const labelEditor = new qx.ui.form.TextField(oldLabel).set({
        placeholder: this.tr("Type text"),
        allowGrowX: true,
        minWidth: labelWidth
      });
      nodeLabelEditor.add(labelEditor, {
        flex: 1
      });

      this.addListener("appear", e => {
        labelEditor.focus();
        if (labelEditor.getValue()) {
          labelEditor.setTextSelection(0, labelEditor.getValue().length);
        }
      }, this);

      // Create the "Save" button to close the cell editor
      const save = this.__save = new qx.ui.form.Button(this.tr("Save"));
      save.set({
        appearance: "form-button",
        padding: [1, 5]
      });
      save.addListener("execute", e => {
        const newLabel = labelEditor.getValue();
        const data = {
          newLabel
        };
        this.fireDataEvent("labelChanged", data);
      }, this);
      nodeLabelEditor.add(save);

      this.add(nodeLabelEditor);
    },

    __addSubtitle: function(subtitleLabel) {
      if (subtitleLabel) {
        const subtitle = new qx.ui.basic.Label(subtitleLabel).set({
          font: "text-12"
        });
        this.add(subtitle);
      }
    },

    __attachEventHandlers: function() {
      let command = new qx.ui.command.Command("Enter");
      command.addListener("execute", e => {
        this.__save.execute();
        command.dispose();
        command = null;
      });

      let commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.close();
        commandEsc.dispose();
        commandEsc = null;
      });
    }
  }
});

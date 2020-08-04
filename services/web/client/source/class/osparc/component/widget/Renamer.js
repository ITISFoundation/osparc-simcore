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
 *   let itemRenamer = new osparc.component.widget.Renamer(selectedItem.getLabel());
 *   itemRenamer.addListener("labelChanged", e => {
 *     const data = e.getData();
 *     const newLabel = data.newLabel;
 *     selectedItem.setLabel(newLabel);
 *   }, this);
 *   itemRenamer.open();
 * </pre>
 */

qx.Class.define("osparc.component.widget.Renamer", {
  extend: osparc.ui.window.Window,

  construct: function(oldLabel) {
    this.base(arguments, "Rename");

    const maxWidth = 350;
    const minWidth = 100;
    const labelWidth = Math.min(Math.max(parseInt(oldLabel.length*4), minWidth), maxWidth);
    this.set({
      appearance: "window-small-cap",
      layout: new qx.ui.layout.HBox(4),
      autoDestroy: true,
      padding: 2,
      modal: true,
      showMaximize: false,
      showMinimize: false,
      width: labelWidth,
      clickAwayClose: true
    });
    this.__populateNodeLabelEditor(oldLabel, labelWidth);
  },

  events: {
    "labelChanged": "qx.event.type.Data"
  },

  members: {
    __populateNodeLabelEditor: function(oldLabel, labelWidth) {
      // Create a text field in which to edit the data
      let labelEditor = new qx.ui.form.TextField(oldLabel).set({
        allowGrowX: true,
        minWidth: labelWidth
      });
      this.add(labelEditor, {
        flex: 1
      });

      this.addListener("appear", e => {
        labelEditor.focus();
        labelEditor.setTextSelection(0, labelEditor.getValue().length);
      }, this);

      // Create the "Save" button to close the cell editor
      let save = new qx.ui.form.Button("Save");
      save.addListener("execute", e => {
        const newLabel = labelEditor.getValue();
        const data = {
          newLabel
        };
        this.fireDataEvent("labelChanged", data);
        this.close();
      }, this);
      this.add(save);

      // Let user press Enter from the cell editor text field to finish.
      let command = new qx.ui.command.Command("Enter");
      command.addListener("execute", e => {
        save.execute();
        command.dispose();
        command = null;
      });

      // Let user press Enter from the cell editor text field to finish.
      let commandEsc = new qx.ui.command.Command("Esc");
      commandEsc.addListener("execute", e => {
        this.close();
        commandEsc.dispose();
        commandEsc = null;
      });
    }
  }
});

qx.Class.define("qxapp.component.widget.TreeItemRenamer", {
  extend: qx.ui.window.Window,

  construct: function(selectedItem) {
    this.base(arguments, "Rename");

    const oldLabel = selectedItem.getLabel();
    const maxWidth = 350;
    const minWidth = 100;
    const labelWidth = Math.min(Math.max(parseInt(oldLabel.length*4), minWidth), maxWidth);
    this.set({
      appearance: "window-small-cap",
      layout: new qx.ui.layout.HBox(4),
      padding: 2,
      modal: true,
      showMaximize: false,
      showMinimize: false,
      width: labelWidth
    });
    this.__populateNodeLabelEditor(selectedItem, labelWidth);
  },

  events: {
    "LabelChanged": "qx.event.type.Data"
  },

  members: {
    __populateNodeLabelEditor: function(selectedItem, labelWidth) {
      const oldLabel = selectedItem.getLabel();

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
        selectedItem.setLabel(newLabel);
        const data = {
          newLabel: newLabel
        };
        this.fireDataEvent("LabelChanged", data);

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

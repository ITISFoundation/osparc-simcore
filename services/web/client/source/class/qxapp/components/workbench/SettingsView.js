qx.Class.define("qxapp.components.workbench.SettingsView", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    let box = new qx.ui.layout.VBox(10);
    box.set({
      alignX: "center"
    });

    this.set({
      layout: box,
      padding: 10
    });

    this.__initTitle();
    this.__initSettings();
  },

  events: {
    "SettingsEditionDone": "qx.event.type.Event",
    "ShowViewer": "qx.event.type.Data"
  },

  properties: {
    node: {
      check: "qxapp.components.workbench.NodeBase",
      apply: "__applyNode"
    }
  },
  members: {
    __settingsBox: null,

    __initTitle: function() {
      let box = new qx.ui.layout.HBox();
      box.set({
        spacing: 10,
        alignX: "right"
      });
      let titleBox = new qx.ui.container.Composite(box);
      let settLabel = new qx.ui.basic.Label(this.tr("Inputs"));
      settLabel.set({
        alignX: "center",
        alignY: "middle"
      });
      let doneBtn = new qx.ui.form.Button(this.tr("Done"));

      titleBox.add(settLabel, {
        width: "75%"
      });
      titleBox.add(doneBtn);
      this.add(titleBox);

      doneBtn.addListener("execute", function() {
        this.fireEvent("SettingsEditionDone");
      }, this);
    },

    __initSettings: function() {
      this.__settingsBox = new qx.ui.container.Composite(new qx.ui.layout.Grow());
      this.add(this.__settingsBox);
    },

    __applyNode: function(node, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__settingsBox.add(node.getPropsWidget());

      // Show viewer
      if (node.getMetadata().viewer) {
        let button = new qx.ui.form.Button("Open Viewer");
        button.setEnabled(node.getMetadata().viewer.port !== null);
        button.addListener("execute", function(e) {
          this.fireDataEvent("ShowViewer", node.getMetadata());
        }, this);
        this.add(button);
      }
    }
  }
});

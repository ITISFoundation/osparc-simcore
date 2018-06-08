qx.Class.define("qxapp.components.workbench.SettingsView", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);
    let grid = new qx.ui.layout.Grid(10, 10);
    grid.setRowFlex(2, 1);
    this._setLayout(grid);
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
    _createChildControlImpl : function(id, hash) {
      let control;

      switch (id) {
        case "title":
          control = new qx.ui.basic.Label(this.getLabel());
          control.setAnonymous(true);
          this._add(control, {
            column: 0,
            row: 1
          });
          break;
        case "close":
          control = new qx.ui.form.Button(null, "@FontAwesomeSolid/times/24").set({
            alignX: "right",
            decorator: null
          });
          control.addListener("execute", () => {
            this.fireEvent("SettingsEditionDone");
          });
          this._add(control, {
            column: 0,
            row: 0
          });
          break;
        case "settings":
          control = new qx.ui.core.Widget();
          control._setLayout(new qx.ui.layout.Grow());
      }
      return control || this.base(arguments, id);
    },

    __applyNode: function(node, oldNode, propertyName) {
      this.__settingsBox.removeAll();
      this.__settingsBox.add(node.getSettingsWidget());
    },

    /**
     * DEPRECATED ... the node settings from is now stored in a property of the node.
     */
    XXXsetNodeMetadata: function(node) {
      this.__settingsBox.removeAll();

      let form = new qx.ui.form.Form();
      {
        // Expose title
        let input = new qx.ui.form.TextField().set({
          value: node.getMetadata().label
        });
        if (input) {
          form.add(input, this.tr("Node Title"), null, "NodeTitle");
        }
      }

      // Expose settings
      for (let i = 0; i < node.getMetadata().settings.length; i++) {
        let sett = node.getMetadata().settings[i];
        let input = this.__fromMetadataToQxSetting(sett);
        if (input) {
          form.add(input, sett.desc, null, sett.key);
        }
      }

      // form with Compute and reset button
      let saveButton = new qx.ui.form.Button(this.tr("Save"));
      form.addButton(saveButton);
      let resetButton = new qx.ui.form.Button(this.tr("Reset"));
      form.addButton(resetButton);

      let controller = new qx.data.controller.Form(null, form);
      let model = controller.createModel();

      saveButton.addListener("execute", function() {
        if (form.validate()) {
          node.getMetadata().label = model.get("NodeTitle");
          node.setServiceName(node.getMetadata().label);

          for (let i = 0; i < node.getMetadata().settings.length; i++) {
            let settKey = node.getMetadata().settings[i].key;
            node.getMetadata().settings[i].value = model.get(settKey);
          }
        }
      }, this);

      resetButton.addListener("execute", function() {
        form.reset();
      }, this);

      this.__settingsBox.add(new qx.ui.form.renderer.Single(form));


      // Show viewer
      if (Object.prototype.hasOwnProperty.call(node.getMetadata(), "viewer")) {
        let button = new qx.ui.form.Button("Open Viewer");
        button.setEnabled(node.getMetadata().viewer.port !== null);
        button.addListener("execute", function(e) {
          this.fireDataEvent("ShowViewer", node.getMetadata());
        }, this);
        this.__settingsBox.add(button);
      }
    },

    __fromMetadataToQxSetting: function(metadata) {
      let input = null;
      switch (metadata.type) {
        case "number": {
          input = new qx.ui.form.Spinner();
          input.set({
            value: metadata.value
          });
          break;
        }
        case "text": {
          input = new qx.ui.form.TextField();
          input.set({
            value: metadata.value
          });
          break;
        }
        case "select": {
          input = new qx.ui.form.SelectBox();
          for (let j = 0; j < metadata.options.length; j++) {
            let optionItem = new qx.ui.form.ListItem(metadata.options[j], null, j);
            input.add(optionItem);
          }
          if (input.getSelectables().length > 0) {
            input.setSelection([input.getSelectables()[metadata.value]]);
          }
          break;
        }
        case "boolean": {
          input = new qx.ui.form.CheckBox();
          input.set({
            value: (metadata.value === 1)
          });
          break;
        }
      }
      return input;
    }
  }
});

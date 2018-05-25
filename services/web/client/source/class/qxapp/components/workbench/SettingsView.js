qx.Class.define("qxapp.components.workbench.SettingsView", {
  extend: qx.ui.container.Composite,

  construct: function() {
    this.base();

    let box = new qx.ui.layout.VBox(10, null, "separator-vertical");
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

  members: {
    __settingsBox: null,

    __initTitle: function() {
      let box = new qx.ui.layout.HBox();
      box.set({
        spacing: 10,
        alignX: "right"
      });
      let titleBox = new qx.ui.container.Composite(box);
      let settLabel = new qx.ui.basic.Label(this.tr("Settings"));
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
      this.__settingsBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this.add(this.__settingsBox);
    },

    setNodeMetadata: function(node) {
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

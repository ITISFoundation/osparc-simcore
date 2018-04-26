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
      padding: 10,
      backgroundColor: "dark-blue" // It is defined in theme/Color
    });

    this._InitTitle();
    this._InitSettings();
  },

  events: {
    "SettingsEditionDone": "qx.event.type.Event"
  },

  members: {
    _settingsBox: null,

    _InitTitle: function() {
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

      let scope = this;
      doneBtn.addListener("execute", function() {
        scope.fireEvent("SettingsEditionDone");
      }, scope);
    },

    _InitSettings: function() {
      this._settingsBox = new qx.ui.container.Composite(new qx.ui.layout.VBox(10));
      this.add(this._settingsBox);
    },

    setNodeMetadata: function(node) {
      this._settingsBox.removeAll();

      let form = new qx.ui.form.Form();
      {
        // Expose title
        let input = new qx.ui.form.TextField().set({
          value: node.getMetaData().name
        });
        if (input) {
          form.add(input, this.tr("Node Title"), null, "NodeTitle");
        }
      }

      // Expose settings
      for (let i = 0; i < node.getMetaData().settings.length; i++) {
        let sett = node.getMetaData().settings[i];
        let input = this._fromMetadataToQxSetting(sett);
        if (input) {
          form.add(input, sett.text, null, sett.name);
        }
      }

      // form with Compute and reset button
      let computeButton = new qx.ui.form.Button(this.tr("Save"));
      form.addButton(computeButton);
      let resetButton = new qx.ui.form.Button(this.tr("Reset"));
      form.addButton(resetButton);

      let controller = new qx.data.controller.Form(null, form);
      let model = controller.createModel();

      computeButton.addListener("execute", function() {
        if (form.validate()) {
          node.getMetaData().name = model.get("NodeTitle");
          node.setServiceName(node.getMetaData().name);

          for (let i = 0; i < node.getMetaData().settings.length; i++) {
            let settKey = node.getMetaData().settings[i].name;
            node.getMetaData().settings[i].value = model.get(settKey);
          }
        }
      }, this);

      resetButton.addListener("execute", function() {
        form.reset();
      }, this);

      this._settingsBox.add(new qx.ui.form.renderer.Single(form));


      // Show viewer
      if (Object.prototype.hasOwnProperty.call(node.getMetaData(), "viewer")) {
        let button = new qx.ui.form.Button("Open Viewer");
        button.setEnabled(node.getMetaData().viewer.port !== null);
        let scope = this;
        button.addListener("execute", function(e) {
          let url = node.getMetaData().viewer.ip + ":" + node.getMetaData().viewer.port;
          let modelerWin = scope.createBrowserWindow(url, node.getMetaData().name);
          modelerWin.open();
          // Too hacky
          scope.getLayoutParent().getChildren()[1]._desktop.add(modelerWin);
        }, scope);
        this._settingsBox.add(button);
      }
    },

    createBrowserWindow: function(url, name) {
      console.log("Accessing:", url);
      let win = new qx.ui.window.Window(name);
      win.setShowMinimize(false);
      win.setLayout(new qx.ui.layout.VBox(5));
      let iframe = new qx.ui.embed.Iframe().set({
        width: 900,
        height: 700,
        minWidth: 500,
        minHeight: 500,
        source: url,
        decorator : null
      });
      win.add(iframe, {
        flex: 1
      });
      // win.setModal(true);
      win.moveTo(150, 150);

      return win;
    },

    _fromMetadataToQxSetting: function(metadata) {
      let input;
      switch (metadata.type) {
        case "number":
          input = new qx.ui.form.Spinner();
          input.set({
            value: metadata.value
          });
          break;
        case "text":
          input = new qx.ui.form.TextField();
          input.set({
            value: metadata.value
          });
          break;
        case "select":
          input = new qx.ui.form.SelectBox();
          for (let j = 0; j < metadata.options.length; j++) {
            let optionItem = new qx.ui.form.ListItem(metadata.options[j], null, j);
            input.add(optionItem);
          }
          if (input.getSelectables().length > 0) {
            input.setSelection([input.getSelectables()[metadata.value]]);
          }
          break;
        case "boolean":
          input = new qx.ui.form.CheckBox();
          input.set({
            value: (metadata.value === 1)
          });
          break;
        default:
          input = null;
          break;
      }
      return input;
    }
  }
});

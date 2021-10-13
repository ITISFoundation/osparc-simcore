/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */


qx.Class.define("osparc.component.node.ParameterEditor", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      node
    });

    this.set({
      appearance: "settings-groupbox",
      maxWidth: 800,
      alignX: "center"
    });
  },

  statics: {
    getParameterOutputTypeFromMD: function(metaData) {
      return metaData["outputs"]["out_1"]["type"];
    },

    getParameterOutputType: function(node) {
      const metaData = node.getMetaData();
      return this.self().getParameterOutputTypeFromMD(metaData);
    },

    setParameterOutputValue: function(node, val) {
      node.setOutputData({
        "out_1": val
      });
    }
  },

  events: {
    "ok": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
    }
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "label":
          control = new qx.ui.form.TextField();
          break;
        case "data-type": {
          control = new qx.ui.form.SelectBox().set({
            allowGrowX: false
          });
          [
            "number",
            "integer",
            "boolean"
          ].forEach(parametrizableType => {
            const parametrizableTypeItem = new qx.ui.form.ListItem(qx.lang.String.firstUp(parametrizableType));
            parametrizableTypeItem.type = parametrizableType;
            control.add(parametrizableTypeItem);
          });
          break;
        }
        case "number":
          control = new qx.ui.form.TextField();
          break;
        case "integer":
          control = new qx.ui.form.Spinner();
          control.set({
            maximum: 10000,
            minimum: -10000
          });
          break;
        case "boolean":
          control = new qx.ui.form.CheckBox();
          break;
        case "cancel-button": {
          control = new qx.ui.form.Button(this.tr("Cancel")).set({
            allowGrowX: false
          });
          const commandEsc = new qx.ui.command.Command("Esc");
          control.setCommand(commandEsc);
          control.addListener("execute", () => this.fireEvent("cancel"));
          break;
        }
        case "ok-button": {
          control = new qx.ui.form.Button(this.tr("OK")).set({
            allowGrowX: false
          });
          control.addListener("execute", () => {
            this.fireEvent("ok");
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    createSimpleForm: function() {
      const form = this.__buildForm(false);
      const node = this.getNode();
      form.getItem("value").addListener("changeValue", e => osparc.component.node.ParameterEditor.setParameterOutputValue(node, e.getData()));
      return new qx.ui.form.renderer.Single(form);
    },

    __createForm: function() {
      const form = this.__buildForm();
      const node = this.getNode();
      form.getItem("label").addListener("changeValue", e => node.setLabel(e.getData()));
      form.getItem("value").addListener("changeValue", e => osparc.component.node.ParameterEditor.setParameterOutputValue(node, e.getData()));
      return new qx.ui.form.renderer.Single(form);
    },

    turnIntoForm: function() {
      const renderer = this.__createForm();
      this._removeAll();
      const settingsGroupBox = osparc.component.node.BaseNodeView.createSettingsGroupBox(this.tr("Settings"));
      this._add(settingsGroupBox);
      settingsGroupBox.add(renderer);
    },

    popUpInWindow: function() {
      const form = this.__buildForm();
      this.__addButtons(form);

      this._removeAll();
      const renderer = new qx.ui.form.renderer.Single(form);
      this._add(renderer);

      const win = osparc.ui.window.Window.popUpInWindow(this, "Edit Parameter", 250, 175);
      this.addListener("ok", () => {
        const node = this.getNode();
        const label = form.getItem("label").getValue();
        node.setLabel(label);
        const val = form.getItem("value").getValue();
        osparc.component.node.ParameterEditor.setParameterOutputValue(node, val);
        win.close();
      }, this);
      this.addListener("cancel", () => {
        win.close();
      }, this);
    },

    __buildForm: function(allSettings = true) {
      const form = new qx.ui.form.Form();

      const node = this.getNode();

      const type = this.self().getParameterOutputType(node);
      if (allSettings) {
        const label = this.getChildControl("label");
        form.add(label, "Label", null, "label");
        label.setValue(node.getLabel());

        const typeBox = this.getChildControl("data-type");
        typeBox.getSelectables().forEach(selectable => {
          if (selectable.type === type) {
            typeBox.setSelection([selectable]);
            typeBox.setEnabled(false);
          }
        });
        form.add(typeBox, "Data Type", null, "type");
      }

      const valueField = this.getChildControl(type);
      const outputs = node.getOutputs();
      if ("value" in outputs["out_1"]) {
        if (["integer", "boolean"].includes(type)) {
          valueField.setValue(outputs["out_1"]["value"]);
        } else {
          valueField.setValue(String(outputs["out_1"]["value"]));
        }
      }
      form.add(valueField, "Value", null, "value");

      return form;
    },

    __addButtons: function(form) {
      // buttons
      const cancelButton = this.getChildControl("cancel-button");
      form.addButton(cancelButton);
      const okButton = this.getChildControl("ok-button");
      form.addButton(okButton);
    }
  }
});

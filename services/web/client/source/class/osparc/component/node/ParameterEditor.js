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
    this.__buildForm();
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
    "editParameter": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
    }
  },

  members: {
    __form: null,

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
            this.fireEvent("editParameter");
          });
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildForm: function() {
      const form = this.__form = new qx.ui.form.Form();
      const renderer = this.__renderer = new qx.ui.form.renderer.Single(form);
      this._add(renderer);

      const node = this.getNode();

      const label = this.getChildControl("label");
      form.add(label, "Label", null, "label");
      label.setValue(node.getLabel());

      const type = this.self().getParameterOutputType(node);
      const typeBox = this.getChildControl("data-type");
      typeBox.getSelectables().forEach(selectable => {
        if (selectable.type === type) {
          typeBox.setSelection([selectable]);
          typeBox.setEnabled(false);
        }
      });
      form.add(typeBox, "Data Type", null, "type");

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

      // buttons
      const cancelButton = this.getChildControl("cancel-button");
      form.addButton(cancelButton);
      const okButton = this.getChildControl("ok-button");
      form.addButton(okButton);
    },

    getLabel: function() {
      return this.__form.getItem("label").getValue();
    },

    getValue: function() {
      const item = this.__form.getItem("value");
      return item.getValue();
    }
  }
});

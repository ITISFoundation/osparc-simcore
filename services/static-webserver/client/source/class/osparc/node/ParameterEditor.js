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


qx.Class.define("osparc.node.ParameterEditor", {
  extend: qx.ui.form.renderer.Single,

  construct: function(node) {
    this.set({
      node
    });

    const form = this.__form = new qx.ui.form.Form();
    this.base(arguments, form);
  },

  statics: {
    getParameterOutputType: function(node) {
      const metadata = node.getMetadata();
      return osparc.service.Utils.getParameterType(metadata);
    },

    setParameterOutputValue: function(node, val) {
      node.setOutputData({
        "out_1": this.self().getParameterOutputType(node) === "array" ? osparc.ui.form.ContentSchemaArray.addArrayBrackets(val) : val
      });
    }
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
        case "string":
        case "number":
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
        case "ref_contentSchema":
        case "array":
          control = new osparc.ui.form.ContentSchemaArray();
          break;
      }
      return control || this.base(arguments, id);
    },

    buildForm: function(allSettings = true) {
      this._removeAll();

      const node = this.getNode();

      const type = this.self().getParameterOutputType(node);
      if (allSettings) {
        const label = this.getChildControl("label");
        label.setValue(node.getLabel());
        label.bind("value", node, "label");
        this.__form.add(label, "Label", null, "label");

        const typeBox = this.getChildControl("data-type");
        typeBox.getSelectables().forEach(selectable => {
          if (selectable.type === type) {
            typeBox.setSelection([selectable]);
            typeBox.setEnabled(false);
          }
        });
        this.__form.add(typeBox, "Data Type", null, "type");
      }

      const valueField = this.getChildControl(type);
      const outputs = node.getOutputs();
      if (type === "ref_contentSchema") {
        valueField.setContentSchema(outputs["out_1"]["contentSchema"]);
      }
      if ("value" in outputs["out_1"]) {
        if (["integer", "boolean"].includes(type)) {
          valueField.setValue(outputs["out_1"]["value"]);
        } else {
          valueField.setValue(String(outputs["out_1"]["value"]));
        }
      }
      valueField.addListener("changeValue", e => osparc.node.ParameterEditor.setParameterOutputValue(node, e.getData()));
      this.__form.add(valueField, "Value", null, "value");
    }
  }
});

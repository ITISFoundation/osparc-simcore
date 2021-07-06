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


qx.Class.define("osparc.component.node.ParameterView", {
  extend: qx.ui.core.Widget,

  construct: function(node) {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());

    this.set({
      node
    });
    this.__buildLayout();
  },

  statics: {
    getParameterOutputType: function(node) {
      const metaData = node.getMetaData();
      return metaData["outputs"]["out_1"]["type"];
    }
  },

  properties: {
    node: {
      check: "osparc.data.model.Node"
    }
  },

  events: {
    "ok": "qx.event.type.Event",
    "cancel": "qx.event.type.Event"
  },

  members: {
    __validField: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "data-type": {
          control = new qx.ui.form.SelectBox();
          [
            "number",
            "integer",
            "boolean"
          ].forEach(parametrizableType => {
            const parametrizableTypeItem = new qx.ui.form.ListItem(qx.lang.String.firstUp(parametrizableType));
            parametrizableTypeItem.type = parametrizableType;
            control.add(parametrizableTypeItem);
          });
          this._add(control);
          break;
        }
        case "number":
          control = new qx.ui.form.TextField();
          this._add(control);
          break;
        case "integer":
          control = new qx.ui.form.Spinner();
          this._add(control);
          break;
        case "boolean":
          control = new qx.ui.form.CheckBox();
          this._add(control);
          break;
        case "buttons-layout":
          control = new qx.ui.container.Composite(new qx.ui.layout.HBox(5).set({
            alignX: "right"
          })).set({
            padding: 2
          });
          this._add(control);
          break;
        case "cancel-button": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button();
          control.addListener("execute", () => this.fireEvent("cancel"));
          buttons.add(control);
          break;
        }
        case "ok-button": {
          const buttons = this.getChildControl("buttons-layout");
          control = new qx.ui.form.Button();
          control.addListener("execute", () => this.fireEvent("ok"));
          buttons.add(control);
          break;
        }
      }
      return control || this.base(arguments, id);
    },

    __buildLayout: function() {
      const node = this.getNode();
      const type = this.self().getParameterOutputType(node);
      const typeBox = this.getChildControl("data-type");
      typeBox.getSelectables().forEach(selectable => {
        if (selectable.type === type) {
          typeBox.setSelection([selectable]);
          typeBox.setEnabled(false);
        }
      });
      this.__valueField = this.getChildControl(type);
    },

    getValue: function() {
      return this.__valueField.getValue();
    }
  }
});

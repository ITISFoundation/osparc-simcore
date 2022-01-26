/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.form.ContentSchemaField", {
  extend: qx.ui.form.TextField,

  construct: function(contentSchema) {
    this.base(arguments);

    if (contentSchema) {
      this.setContentSchema(contentSchema);
    }
  },

  properties: {
    contentSchema: {
      check: "Object",
      init: null,
      nullable: true
    }
  },

  members: {
    // overrriden
    getValue: function() {
      let value = this.base(arguments);
      const cSchema = this.getContentSchema();
      if (cSchema) {
        if (cSchema.type === "array") {
          value = this.__addArrayBrackets(value);
        }
      }
      return value;
    },

    // overrriden
    setValue: function(value) {
      const cSchema = this.getContentSchema();
      if (cSchema) {
        if (cSchema.type === "array") {
          value = this.__addArrayBrackets(value);
        }
      }
      this.base(arguments, value);
    },

    __addArrayBrackets: function(label) {
      if (label.charAt(0) !== "[") {
        label = "[" + label;
      }
      if (label.charAt(label.length-1) !== "]") {
        label += "]";
      }
      return label;
    }
  }
});

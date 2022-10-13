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

qx.Class.define("osparc.ui.form.ContentSchemaArray", {
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
      nullable: true,
      apply: "__applyContentSchema"
    },

    validator: {
      check: "qx.ui.form.validation.Manager",
      init: null,
      nullable: true
    }
  },

  statics: {
    addArrayBrackets: function(label) {
      if (label.charAt(0) !== "[") {
        label = "[" + label;
      }
      if (label.charAt(label.length-1) !== "]") {
        label += "]";
      }
      return label;
    }
  },

  members: {
    // overrriden
    getValue: function() {
      let value = this.base(arguments);
      if (value === null) {
        value = "";
      }
      const cSchema = this.getContentSchema();
      if (cSchema) {
        if (cSchema.type === "array") {
          value = this.self().addArrayBrackets(value);
        }
      }
      return value;
    },

    // overrriden
    setValue: function(value) {
      const cSchema = this.getContentSchema();
      if (cSchema) {
        if (cSchema.type === "array") {
          if (Array.isArray(value)) {
            value = JSON.stringify(value);
          }
          value = this.self().addArrayBrackets(value);
        }
      }
      this.base(arguments, value);
    },

    __applyContentSchema: function(contentSchema) {
      const isValidatable = Object.keys(contentSchema).some(r => ["items", "minItems", "maxItems"].indexOf(r) >= 0);
      if (isValidatable) {
        const validator = osparc.ui.form.ContentSchemaHelper.createArrayValidator(this, contentSchema);
        this.setValidator(validator);
      }
    }
  }
});

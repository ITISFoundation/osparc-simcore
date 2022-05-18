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
        const manager = new qx.ui.form.validation.Manager();
        manager.add(this, (valuesInString, item) => {
          let multiplier = 1;
          let invalidMessage = qx.locale.Manager.tr("Out of range");
          if ("x_unit" in contentSchema) {
            const {
              unitPrefix
            } = osparc.utils.Units.decomposeXUnit(contentSchema["x_unit"]);
            multiplier = osparc.utils.Units.getMultiplier(unitPrefix, this.unitPrefix);
          }
          let valid = true;
          if ("items" in contentSchema) {
            const values = JSON.parse(valuesInString);
            if ("minimum" in contentSchema["items"] && values.some(v => v < multiplier*(contentSchema["items"].minimum))) {
              valid = false;
              invalidMessage += "<br>";
              invalidMessage += qx.locale.Manager.tr("Minimum value: ") + multiplier*(contentSchema["items"].minimum);
            }
            if ("maximum" in contentSchema["items"] && values.some(v => v > multiplier*(contentSchema["items"].maximum))) {
              valid = false;
              invalidMessage += "<br>";
              invalidMessage += qx.locale.Manager.tr("Maximum value: ") + multiplier*(contentSchema["items"].maximum);
            }
          }
          if (!valid) {
            item.setInvalidMessage(invalidMessage);
          }
          return Boolean(valid);
        });
        this.setValidator(manager);
      }
    }
  }
});

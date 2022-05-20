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

qx.Class.define("osparc.ui.form.ContentSchemaHelper", {
  type: "static",

  statics: {
    getDomainText: function(s) {
      let rangeText = null;
      if ("minimum" in s && "maximum" in s) {
        rangeText = `&isin; [${s.minimum}, ${s.maximum}] `;
      } else if ("minimum" in s) {
        rangeText = `&isin; [${s.minimum}, &infin;] `;
      } else if ("maximum" in s) {
        rangeText = `&isin; [-&infin;, ${s.maximum}] `;
      }
      if (rangeText && "x_unit" in s) {
        const {
          unitPrefix,
          unit
        } = osparc.utils.Units.decomposeXUnit(s["x_unit"]);
        const labels = osparc.utils.Units.getLabels(unit, unitPrefix);
        if (labels !== null) {
          rangeText += labels.unitShort;
        }
      }
      return rangeText;
    },

    createValidator: function(control, s) {
      const manager = new qx.ui.form.validation.Manager();
      manager.add(control, (value, item) => {
        let multiplier = 1;
        let invalidMessage = qx.locale.Manager.tr("Out of range");
        if ("x_unit" in s) {
          const {
            unitPrefix
          } = osparc.utils.Units.decomposeXUnit(s["x_unit"]);
          multiplier = osparc.utils.Units.getMultiplier(unitPrefix, control.unitPrefix);
        }
        let valid = true;
        if ("minimum" in s && value < multiplier*(s.minimum)) {
          valid = false;
          invalidMessage += "<br>";
          invalidMessage += qx.locale.Manager.tr("Minimum value: ") + multiplier*(s.minimum);
        }
        if ("maximum" in s && value > multiplier*(s.maximum)) {
          valid = false;
          invalidMessage += "<br>";
          invalidMessage += qx.locale.Manager.tr("Maximum value: ") + multiplier*(s.maximum);
        }
        if (!valid) {
          item.setInvalidMessage(invalidMessage);
        }
        return Boolean(valid);
      });
      return manager;
    },

    getArrayDomainText: function(s) {
      const s2 = osparc.utils.Utils.deepCloneObject(s);
      if ("items" in s2) {
        Object.keys(s2.items).forEach(item => {
          s2[item] = s2.items[item];
        });
      }
      let rangeText = this.getDomainText(s2.items);
      if (rangeText === null) {
        rangeText = "";
      }
      if ("minItems" in s) {
        rangeText += "<br>";
        rangeText += qx.locale.Manager.tr("Minimum items: ") + s.minItems;
      }
      if ("maxItems" in s) {
        rangeText += "<br>";
        rangeText += qx.locale.Manager.tr("Maximum items: ") + s.maxItems;
      }
      return rangeText;
    },

    createArrayValidator: function(control, s) {
      const manager = new qx.ui.form.validation.Manager();
      manager.add(control, (valuesInString, item) => {
        const values = JSON.parse(valuesInString);
        if ("minItems" in s && (values.length < s.minItems)) {
          let oorInvalidMessage = qx.locale.Manager.tr("Minimum items: ") + s.minItems;
          item.setInvalidMessage(oorInvalidMessage);
          return false;
        }
        if ("maxItems" in s && (values.length > s.maxItems)) {
          let oorInvalidMessage = qx.locale.Manager.tr("Maximum items: ") + s.maxItems;
          item.setInvalidMessage(oorInvalidMessage);
          return false;
        }
        let multiplier = 1;
        let oorInvalidMessage = qx.locale.Manager.tr("Out of range");
        if ("x_unit" in s) {
          const {
            unitPrefix
          } = osparc.utils.Units.decomposeXUnit(s["x_unit"]);
          multiplier = osparc.utils.Units.getMultiplier(unitPrefix, control.unitPrefix);
        }
        let valid = true;
        if ("items" in s) {
          if ("minimum" in s["items"] && values.some(v => v < multiplier*(s["items"].minimum))) {
            valid = false;
            oorInvalidMessage += "<br>";
            oorInvalidMessage += qx.locale.Manager.tr("Minimum value: ") + multiplier*(s["items"].minimum);
          }
          if ("maximum" in s["items"] && values.some(v => v > multiplier*(s["items"].maximum))) {
            valid = false;
            oorInvalidMessage += "<br>";
            oorInvalidMessage += qx.locale.Manager.tr("Maximum value: ") + multiplier*(s["items"].maximum);
          }
        }
        if (!valid) {
          item.setInvalidMessage(oorInvalidMessage);
        }
        return Boolean(valid);
      });
      return manager;
    }
  }
});

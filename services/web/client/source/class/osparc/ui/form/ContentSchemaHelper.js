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
        rangeText = qx.locale.Manager.tr("Domain ");
        rangeText += `[${s.minimum}, ${s.maximum}]`;
      } else if ("minimum" in s) {
        rangeText = qx.locale.Manager.tr("Domain ");
        rangeText += `[${s.minimum}, &infin;]`;
      } else if ("maximum" in s) {
        rangeText = qx.locale.Manager.tr("Domain ");
        rangeText += `[-&infin;, ${s.maximum}]`;
      }
      if ("x_unit" in s) {
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
          multiplier = osparc.utils.Units.getMultiplier(s, control.unitPrefix, item.unitPrefix);
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
    }
  }
});

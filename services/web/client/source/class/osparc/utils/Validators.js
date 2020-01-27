/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

/**
 * Static class that holds reusable form validators.
 */
qx.Class.define("osparc.utils.Validators", {
  statics: {
    hexColor: function(color, item) {
      const valid = qx.util.ColorUtil.isHex3String(color) || qx.util.ColorUtil.isHex6String(color);
      if (!valid) {
        item.setInvalidMessage(qx.locale.Manager.tr("Color must be in hexadecimal form"));
      }
      return valid;
    }
  }
});

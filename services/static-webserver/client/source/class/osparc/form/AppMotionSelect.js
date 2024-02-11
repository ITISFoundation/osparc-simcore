/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2023 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.form.AppMotionSelect", {
  extend: qx.ui.form.SelectBox,
  construct: function() {
    this.base(arguments);
    this.set({
      appearance: "appmotion-buy-credits-select"
    });
  }
});

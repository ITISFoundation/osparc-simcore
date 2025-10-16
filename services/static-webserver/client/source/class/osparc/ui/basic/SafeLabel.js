/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * A Label that sanitizes its value when in rich mode to avoid XSS attacks
 */

qx.Class.define("osparc.ui.basic.SafeLabel", {
  extend: qx.ui.basic.Label,

  construct() {
    this.base(arguments);

    this.set({
      rich: true,
    });

    this.addListener("changeValue", this._onChangeValue, this);
  },

  members: {
    _onChangeValue(e) {
      const val = e.getData();
      if (typeof val === "string") {
        const sanitized = osparc.wrapper.DOMPurify.sanitize(val);
        if (sanitized !== val) {
          this.setValue(sanitized);
        }
      }
    }
  }
});

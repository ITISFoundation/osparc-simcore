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
 * Based on the single renderer {@link qx.ui.form.renderer.SinglePlaceholder}.
 * Just a more relaxed version with more spacing and transparent backgrounds.
 */
qx.Class.define("osparc.ui.form.renderer.LoginSinglePlaceholder", {
  extend: qx.ui.form.renderer.SinglePlaceholder,

  construct: function(form) {
    this.base(arguments, form);

    this._getLayout().setSpacing(10);
  },

  members: {
    addItems : function(items, names, title) {
      this.base(arguments, items, names, title);

      items.forEach(item => item.setBackgroundColor("transparent"));
    }
  }
});

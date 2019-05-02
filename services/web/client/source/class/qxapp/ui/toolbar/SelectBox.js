/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * SelectBox adapted to be shown inside a toolbar.
 */
qx.Class.define("qxapp.ui.toolbar.SelectBox", {
  extend: qx.ui.form.SelectBox,
  construct: function() {
    this.base(arguments);
  }
});

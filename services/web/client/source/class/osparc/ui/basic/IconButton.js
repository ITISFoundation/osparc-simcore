/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * Small and simple icon button to trigger different actions on tap.
 */
qx.Class.define("osparc.ui.basic.IconButton", {
  extend: qx.ui.basic.Image,

  /**
   * Constructor for IconButton. It takes the icon id that will be converted into a button and a callback function
   * that will be executed whenever the button is clicked.
   *
   * @param {String} icon Clickable icon to display.
   * @param {function} cb Callback function to be executed on tap.
   * @param {object} context Execution context (this) of the callback function.
   */
  construct: function(icon, cb, context) {
    this.base(arguments, icon);
    if (cb) {
      this.addListener("tap", cb, context);
    }
    this.setCursor("pointer");
  }
});

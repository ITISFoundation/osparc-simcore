/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 * Label with osparc.theme.Font.fonts font set
 */

qx.Class.define("osparc.ui.basic.Label", {
  extend: qx.ui.basic.Label,

  /**
   * @param size {Number} Size of the Label
   * @param bold {Boolean} True if bold
   */
  construct: function(size, bold) {
    this.base(arguments);

    this.set({
      font: osparc.ui.basic.Label.getFont(size, bold)
    });
  },

  statics: {
    getFont: function(size=14, bold=false) {
      if (bold) {
        return qx.bom.Font.fromConfig(osparc.theme.Font.fonts["title-"+size]);
      }
      return qx.bom.Font.fromConfig(osparc.theme.Font.fonts["text-"+size]);
    }
  }
});

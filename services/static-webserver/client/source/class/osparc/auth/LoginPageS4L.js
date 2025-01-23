/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Pedro Crespo (pcrespov)

************************************************************************ */

/**
 *  Main Authentication Page:
 *    A multi-page view that fills all page
 */

qx.Class.define("osparc.auth.LoginPageS4L", {
  extend: osparc.auth.LoginPageSplit,

  members: {
    // overridden
    _reloadLayout: function() {
      this.base(arguments);

      this.setBackgroundColor("rgba(0, 20, 46, 1)");
    },

    // overridden
    _getBackgroundImage: function() {
      let backgroundImage = "";

      const defaultBG = `url(${osparc.product.Utils.getProductBackgroundUrl("Sim4Life-head-default.png")}), url(${osparc.product.Utils.getProductBackgroundUrl("clouds_11.png")})`;
      const liteBG = `url(${osparc.product.Utils.getProductBackgroundUrl("Sim4Life-head-lite.png")}), url(${osparc.product.Utils.getProductBackgroundUrl("clouds_11.png")})`;
      const academyBG = `url(${osparc.product.Utils.getProductBackgroundUrl("Sim4Life-head-academy.png")}), url(${osparc.product.Utils.getProductBackgroundUrl("clouds_11.png")})`;

      switch (osparc.product.Utils.getProductName()) {
        case "s4llite":
          backgroundImage = liteBG;
          break;
        case "s4lacad":
        case "s4ldesktopacad":
          backgroundImage = academyBG;
          break;
        case "s4ldesktop":
        case "s4l":
        default:
          backgroundImage = defaultBG;
          break;
      }
      return backgroundImage;
    },
  }
});

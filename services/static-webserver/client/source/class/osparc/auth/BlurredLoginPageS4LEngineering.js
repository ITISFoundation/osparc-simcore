/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2024 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.auth.BlurredLoginPageS4LEngineering", {
  extend: qx.ui.core.Widget,

  members: {
    // overridden
    _reloadLayout: function() {
      const layout = new qx.ui.layout.HBox();
      this._setLayout(layout);

      this.setBackgroundColor("primary-background-color");

      this._removeAll();

      this.__setBackgroundImage();

    },

    __setBackgroundImage: function() {
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
      this._setBackgroundImage(backgroundImage);
    }
  }
});

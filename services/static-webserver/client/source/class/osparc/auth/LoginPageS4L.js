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
  extend: osparc.auth.LoginPageFlex,

  members: {
    // overridden
    _reloadLayout: function() {
      const layout = new qx.ui.layout.HBox();
      this._setLayout(layout);

      this.setBackgroundColor("primary-background-color");

      this._removeAll();

      const loginLayout = this._getMainLayout();
      if (this.isCompactVersion()) {
        this._resetBackgroundImage();
        this._add(loginLayout, {
          flex: 1
        });
      } else {
        this.__setBackgroundImage();
        this._add(new qx.ui.core.Spacer(), {
          width: "50%"
        });
        this._add(loginLayout, {
          width: "50%"
        });
      }
    },

    __setBackgroundImage: function() {
      let backgroundImage = "";

      // const defaultBG = "url(resource/osparc/Sim4Life_login_page_master_transparent_bg.png)";
      const defaultBG = "url(resource/osparc/Sim4Life_Science.png)";

      switch (osparc.product.Utils.getProductName()) {
        case "s4llite":
          backgroundImage = defaultBG;
          break;
        case "s4lacad":
          backgroundImage = defaultBG;
          break;
        case "s4ldesktop":
          backgroundImage = defaultBG;
          break;
        case "s4ldesktopacad":
          backgroundImage = defaultBG;
          break;
        case "s4l":
        default:
          backgroundImage = defaultBG;
          break;
      }
      this._setBackgroundImage(backgroundImage);
    }
  }
});

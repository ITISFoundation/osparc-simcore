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

      const defaultBG = "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/front.png)," +
        "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/Speag_Sim4Life_Intro_Head_default.png)," +
        "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/back.png)";

      const liteBG = "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/front.png)," +
        "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/Speag_Sim4Life_Intro_Head_3.png)," +
        "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/back.png)";

      const academyBG = "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/front.png)," +
        "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/Speag_Sim4Life_Intro_Head_1.png)," +
        "url(https://raw.githubusercontent.com/ZurichMedTech/s4l-assets/main/app/full/background-images/S4L/test-images/back.png)";

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

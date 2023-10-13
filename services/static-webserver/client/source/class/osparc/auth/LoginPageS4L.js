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

      this.setBackgroundColor("#025887");

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
      switch (osparc.product.Utils.getProductName()) {
        case "s4llite":
          backgroundImage = "url(resource/osparc/s4llite_splitimage.png)";
          break;
        case "s4lacad":
        case "s4lacaddesktop":
          backgroundImage = "url(resource/osparc/s4lacad_splitimage.png)";
          break;
        default:
          backgroundImage = "url(resource/osparc/s4l_splitimage.png)";
          break;
      }
      this._setBackgroundImage(backgroundImage);
    }
  }
});

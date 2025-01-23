/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2022 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

/**
 *  Main Authentication Page:
 *    A multi-page view that fills all page
 */

qx.Class.define("osparc.auth.LoginPageTI", {
  extend: osparc.auth.LoginPageSplit,

  members: {
    _getBackgroundImage: function() {
      const backgroundImage = "url(resource/osparc/tip_splitimage.png)";
      return backgroundImage;
    }
  }
});

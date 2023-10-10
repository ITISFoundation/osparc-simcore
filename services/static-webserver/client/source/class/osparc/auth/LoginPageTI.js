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
  extend: osparc.auth.LoginPage,

  members: {
    // overridden
    _buildLayout: function() {
      const layout = new qx.ui.layout.HBox();
      this._setLayout(layout);

      this.getContentElement().setStyles({
        "background-image": "url(resource/osparc/tip_splitimage.png)",
        "background-repeat": "no-repeat",
        "background-size": "contain"
      });

      this._add(new qx.ui.core.Spacer(), {
        width: "50%"
      });

      const loginLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        alignX: "center",
        alignY: "middle"
      });
      this._add(loginLayout, {
        width: "50%"
      });

      loginLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      const image = this._getLogoWPlatform();
      loginLayout.add(image);

      const pages = this._getLoginStack();
      loginLayout.add(pages);

      const versionLink = this._getVersionLink();
      loginLayout.add(versionLink);

      loginLayout.add(new qx.ui.core.Spacer(), {
        flex: 1
      });
    }
  }
});

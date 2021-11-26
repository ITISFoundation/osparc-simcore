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
  extend: osparc.auth.LoginPage,

  /*
  *****************************************************************************
     CONSTRUCTOR
  *****************************************************************************
  */
  construct: function() {
    this.base(arguments);
  },

  events: {
    "done": "qx.event.type.Data"
  },

  members: {
    // overridden
    _buildLayout: function() {
      const layout = new qx.ui.layout.HBox();
      this._setLayout(layout);

      this.setBackgroundColor("#025887");
      this.getContentElement().setStyles({
        "background-image": "url(resource/osparc/s4l_splitimage.jpeg)",
        "background-repeat": "no-repeat",
        "background-size": "auto 100%"
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

      // styling
      pages.getChildren().forEach(page => {
        page.getChildren().forEach(child => {
          if ("getChildren" in child) {
            child.getChildren().forEach(chil => {
              // "Create account" and "Forgot password"
              chil.set({
                textColor: "#ddd"
              });
            });
          }
        });
      });
      // the double semicolon
      versionLink.set({
        textColor: "#bbb"
      });
      // the two texts
      versionLink.getChildren().forEach(page => {
        page.set({
          textColor: "#bbb"
        });
      });
    }
  }
});

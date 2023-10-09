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

  properties: {
    compactVersion: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeCompactVersion",
      apply: "__reloadLayout"
    }
  },

  events: {
    "done": "qx.event.type.Data"
  },

  members: {
    // overridden
    _buildLayout: function() {
      this.__reloadLayout();

      setTimeout(() => this.__resized(), 100);
      window.addEventListener("resize", () => this.__resized());
    },

    __resized: function() {
      const width = document.documentElement.clientWidth;
      this.setCompactVersion(width < 800);
    },

    __reloadLayout: function() {
      const layout = new qx.ui.layout.HBox();
      this._setLayout(layout);

      this.setBackgroundColor("#025887");

      this._removeAll();

      const loginLayout = this.__getLoginLayout();
      if (this.isCompactVersion()) {
        this.__resetBackgroundImage();
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
          backgroundImage = "url(resource/osparc/s4lacad_splitimage.png)";
          break;
        default:
          backgroundImage = "url(resource/osparc/s4l_splitimage.jpeg)";
          break;
      }
      this.getContentElement().setStyles({
        "background-image": backgroundImage,
        "background-repeat": "no-repeat",
        "background-size": "auto 100%"
      });
    },

    __resetBackgroundImage: function() {
      this.getContentElement().setStyles({
        "background-image": "",
        "background-repeat": "no-repeat",
        "background-size": "auto 100%"
      });
    },

    __getLoginLayout: function() {
      const loginLayout = new qx.ui.container.Composite(new qx.ui.layout.VBox(10)).set({
        alignX: "center",
        alignY: "middle"
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
            child.getChildren().forEach(c => {
              // "Create account" and "Forgot password"
              c.set({
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
        if (page.setTextColor) {
          page.setTextColor("#bbb");
        }
      });

      const scrollView = new qx.ui.container.Scroll();
      scrollView.add(loginLayout);
      return scrollView;
    }
  }
});

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2023 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.auth.LoginPageSplit", {
  extend: qx.ui.core.Widget,
  type: "abstract",

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox();
    this._setLayout(layout);

    this.__rebuildLayout();

    setTimeout(() => this.__resized(), 100);
    window.addEventListener("resize", () => this.__resized());
  },

  properties: {
    compactVersion: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeCompactVersion",
      apply: "__rebuildLayout"
    }
  },

  events: {
    "done": "qx.event.type.Data",
  },

  statics: {
    COMPACT_WIDTH_BREAKPOINT: 2*(osparc.auth.core.BaseAuthPage.FORM_WIDTH + 50),
    COMPACT_HEIGHT_BREAKPOINT: osparc.WindowSizeTracker.HEIGHT_BREAKPOINT * 1.1,
  },

  members: {
    _getBackgroundImage: function() {
      throw new Error("Abstract method called!");
    },

    __resized: function() {
      const width = document.documentElement.clientWidth;
      const height = document.documentElement.clientHeight;
      this.setCompactVersion(
        (width < this.self().COMPACT_WIDTH_BREAKPOINT) ||
        (height < this.self().COMPACT_HEIGHT_BREAKPOINT)
      );
    },

    __rebuildLayout: function() {
      this._removeAll();

      const loginPage = new osparc.auth.LoginPage();
      loginPage.addListener("done", e => this.fireDataEvent("done", e.getData()));
      const hideableItems = loginPage.getChildControl("login-view").getHideableItems();
      if (this.isCompactVersion()) {
        // no split-image
        // just the login widget
        this.__resetBackgroundImage();
        this._add(loginPage, {
          flex: 1
        });
        hideableItems.forEach(hideableItem => hideableItem.exclude());
      } else {
        // split-image on the left
        // the login widget on the right
        this.___setBackgroundImage();
        this._add(new qx.ui.core.Spacer(), {
          width: "50%"
        });
        this._add(loginPage, {
          width: "50%"
        });
        hideableItems.forEach(hideableItem => hideableItem.show());
      }
    },

    __setBackgroundImage: function(backgroundImage) {
      if (osparc.product.Utils.getProductName().includes("s4l")) {
        this.getContentElement().setStyles({
          "background-image": backgroundImage,
          "background-repeat": "no-repeat",
          "background-size": "65% auto, 80% auto", // auto width, 85% height
          "background-position": "left bottom, left -440px bottom -230px" // left bottom
        });
      } else {
        this.getContentElement().setStyles({
          "background-image": backgroundImage,
          "background-repeat": "no-repeat",
          "background-size": "50% auto", // 50% of the view width
          "background-position": "left 10% center" // left bottom
        });
      }
    },

    __resetBackgroundImage: function() {
      this.getContentElement().setStyles({
        "background-image": ""
      });
    },

    ___setBackgroundImage: function() {
      const backgroundImage = this._getBackgroundImage();
      this.__setBackgroundImage(backgroundImage);
    },
  }
});

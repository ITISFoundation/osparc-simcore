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
  extend: osparc.auth.LoginPage,
  type: "abstract",

  properties: {
    compactVersion: {
      check: "Boolean",
      init: false,
      nullable: false,
      event: "changeCompactVersion",
      apply: "_reloadLayout"
    }
  },

  statics: {
    COMPACT_WIDTH_BREAKPOINT: 2*(osparc.auth.core.BaseAuthPage.FORM_WIDTH + 50),
    COMPACT_HEIGHT_BREAKPOINT: osparc.WindowSizeTracker.HEIGHT_BREAKPOINT * 1.1,
  },

  members: {
    // overridden
    _buildLayout: function() {
      this._reloadLayout();

      setTimeout(() => this.__resized(), 100);
      window.addEventListener("resize", () => this.__resized());
    },

    __resized: function() {
      const width = document.documentElement.clientWidth;
      const height = document.documentElement.clientHeight;
      this.setCompactVersion(
        (width < this.self().COMPACT_WIDTH_BREAKPOINT) ||
        (height < this.self().COMPACT_HEIGHT_BREAKPOINT)
      );
    },

    _reloadLayout: function() {
      const layout = new qx.ui.layout.HBox();
      this._setLayout(layout);
      this._removeAll();

      const loginLayout = this._getMainLayout();
      const hideableItems = this.getChildControl("login-view").getHideableItems();
      if (this.isCompactVersion()) {
        // no split-image
        // just the login widget
        this._resetBackgroundImage();
        this._add(loginLayout, {
          flex: 1
        });
        hideableItems.forEach(hideableItem => hideableItem.exclude());
      } else {
        // split-image on the left
        // the login widget on the right
        this.__setBackgroundImage();
        this._add(new qx.ui.core.Spacer(), {
          width: "50%"
        });
        this._add(loginLayout, {
          width: "50%"
        });
        hideableItems.forEach(hideableItem => hideableItem.show());
      }
    },

    _getBackgroundImage: function() {
      throw new Error("Abstract method called!");
    },

    __setBackgroundImage: function() {
      const backgroundImage = this._getBackgroundImage();
      this._setBackgroundImage(backgroundImage);
    }
  }
});

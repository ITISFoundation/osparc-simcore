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

qx.Class.define("osparc.auth.LoginPageFlex", {
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

  members: {
    // overridden
    _buildLayout: function() {
      this._reloadLayout();

      //  Buggy: If the user gets into a page that it's not the Login,
      // after reloading the layout the Login page will be loaded.
      // setTimeout(() => this.__resized(), 100);
      // window.addEventListener("resize", () => this.__resized());
    },

    __resized: function() {
      const width = document.documentElement.clientWidth;
      this.setCompactVersion(width < 2*(osparc.auth.core.BaseAuthPage.FORM_WIDTH + 50));
    },

    _reloadLayout: function() {
      throw new Error("Abstract method called!");
    }
  }
});

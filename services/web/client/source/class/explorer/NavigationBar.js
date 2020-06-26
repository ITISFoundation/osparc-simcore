/* ************************************************************************

   explorer - an entry point to oSparc

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("explorer.NavigationBar", {
  extend: osparc.desktop.NavigationBar,

  members: {
    buildLayout: function() {
      this.getChildControl("logo");
      this.getChildControl("platform");

      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this.getChildControl("user-manual");
      this.getChildControl("feedback");
      this.getChildControl("theme-switch");
    }
  }
});

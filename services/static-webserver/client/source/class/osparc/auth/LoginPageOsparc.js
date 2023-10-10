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

qx.Class.define("osparc.auth.LoginPageOsparc", {
  extend: osparc.auth.LoginPage,

  members: {
    // overridden
    _buildLayout: function() {
      const layout = new qx.ui.layout.HBox();
      this._setLayout(layout);

      const loginLayout = this._getMainLayout();
      this._add(loginLayout, {
        flex: 1
      });
    }
  }
});

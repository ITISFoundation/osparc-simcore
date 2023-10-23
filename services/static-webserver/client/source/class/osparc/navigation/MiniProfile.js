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

qx.Class.define("osparc.navigation.MiniProfile", {
  extend: qx.ui.menu.Button,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.VBox());
    this._add(osparc.desktop.credits.MyAccount.createMiniProfileView());
  },

  members: {
    // override
    _onPointerOver: function() {
      return;
    }
  }
});

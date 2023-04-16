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

qx.Class.define("osparc.ui.form.HoverMenuButton", {
  extend: qx.ui.form.MenuButton,

  construct: function(label, icon, menu) {
    this.base(arguments, label, icon, menu);

    this.set({
      backgroundColor: "transparent"
    });
  },

  members: {
    // overriden
    _onPointerOver: function() {
      this.base(arguments);

      this.open();
    },

    // overriden
    _applyMenu: function(menu) {
      this.base(arguments, menu);

      menu.set({
        padding: 10,
        backgroundColor: "background-main-1"
      });

      menu.getContentElement().setStyles({
        "border-width": "0px"
      });
    }
  }
});

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
    _onPointerOut: function() {
      this.base(arguments);

      /*
      if (this.getMenu() && this.getMenu().isVisible()) {
        const menu = this.getMenu();
        this.getMenu().addListener("pointerout", e => {
          if (!qx.ui.core.Widget.contains(menu, e.getRelatedTarget())) {
            this.getMenu().exclude();
          }
        });
      }
      */
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

/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2025 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.NewPlusMenu", {
  extend: qx.ui.menu.Menu,

  construct: function() {
    this.base(arguments);

    osparc.utils.Utils.prettifyMenu(this);

    this.set({
      position: "bottom-left",
      padding: 10,
    });

    this.__addItems();
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "new-folder":
          control = new qx.ui.menu.Button().set({
            label: this.tr("New Folder"),
            icon: osparc.dashboard.CardBase.NEW_ICON + "14",
            font: "text-14",
          });
          this.add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __addItems: function() {
      this.getChildControl("new-folder");
    }
  },
});

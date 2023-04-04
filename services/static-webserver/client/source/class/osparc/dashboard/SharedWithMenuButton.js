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

qx.Class.define("osparc.dashboard.SharedWithMenuButton", {
  extend: qx.ui.form.MenuButton,

  construct: function(resource = "study") {
    this.base(arguments, this.tr("Shared with"), "@FontAwesome5Solid/chevron-down/10");

    osparc.utils.Utils.setIdToWidget(this, "sharedWithButton");

    const sharedWithMenu = new qx.ui.menu.Menu().set({
      font: "text-14"
    });
    this.setMenu(sharedWithMenu);

    const options = osparc.dashboard.SearchBarFilter.getSharedWithOptions(resource);
    options.forEach((option, idx) => {
      const btn = new qx.ui.menu.Button(option.label);
      btn.btnId = option.id;
      btn.btnLabel = option.label;
      sharedWithMenu.add(btn);

      btn.addListener("execute", () => this.__buttonExecuted(btn));

      if (idx === 0) {
        btn.execute();
      }
    });
  },

  events: {
    "sharedWith": "qx.event.type.Data"
  },

  members: {
    __buttons: null,

    __buttonExecuted: function(btn) {
      this.set({
        label: btn.getLabel(),
        icon: btn.getIcon()
      });

      const data = {
        "id": btn.btnId,
        "label": btn.btnLabel
      };
      this.fireDataEvent("sharedWith", data);
    }
  }
});

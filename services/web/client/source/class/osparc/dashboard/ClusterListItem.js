/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2021 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.dashboard.ClusterListItem", {
  extend: osparc.dashboard.ServiceBrowserListItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    accessRights: {
      check: "Object",
      nullable: false,
      apply: "_applyAccessRights",
      event: "changeAcessRights"
    }
  },

  events: {
    "openEditCluster": "qx.event.type.Data",
    "deleteCluster": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "options": {
          const iconSize = 25;
          control = new qx.ui.form.MenuButton().set({
            maxWidth: iconSize,
            maxHeight: iconSize,
            alignX: "center",
            alignY: "middle",
            icon: "@FontAwesome5Solid/ellipsis-v/"+(iconSize-11),
            focusable: false
          });
          this._add(control, {
            row: 0,
            column: 3,
            rowSpan: 2
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    _applyAccessRights: function(value) {
      if (value === null) {
        return;
      }
      if (value.getDelete()) {
        const optionsMenu = this.getChildControl("options");
        const menu = this.__getOptionsMenu();
        optionsMenu.setMenu(menu);
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const editClusterButton = new qx.ui.menu.Button(this.tr("Edit details"));
      editClusterButton.addListener("execute", () => {
        this.fireDataEvent("openEditCluster", this.getKey());
      });
      menu.add(editClusterButton);

      const deleteClusterButton = new qx.ui.menu.Button(this.tr("Delete"));
      deleteClusterButton.addListener("execute", () => {
        this.fireDataEvent("deleteCluster", this.getKey());
      });
      menu.add(deleteClusterButton);

      return menu;
    }
  }
});

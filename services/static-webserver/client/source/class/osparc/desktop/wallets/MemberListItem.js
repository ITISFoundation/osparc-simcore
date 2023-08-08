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

qx.Class.define("osparc.desktop.wallets.MemberListItem", {
  extend: osparc.ui.list.ListItemWithMenu,

  properties: {
    gid: {
      check: "Number",
      init: null,
      nullable: false,
      event: "changeGid"
    }
  },

  events: {
    "promoteToAccountant": "qx.event.type.Data",
    "demoteToMember": "qx.event.type.Data",
    "removeMember": "qx.event.type.Data"
  },

  members: {
    // overridden
    _applySubtitleMD: function(value) {
      this.base(arguments, value);

      // highlight me
      const email = osparc.auth.Data.getInstance().getEmail();
      if (email === value) {
        this.addState("selected");
      }
    },

    // overridden
    _setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const subtitle = this.getChildControl("contact");
      if ("getWrite" in accessRights && accessRights.getWrite()) {
        subtitle.setValue(osparc.data.Roles.WALLET[2].longLabel);
      } else if ("getRead" in accessRights && accessRights.getRead()) {
        subtitle.setValue(osparc.data.Roles.WALLET[1].longLabel);
      }
    },

    // overridden
    _getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const accessRights = this.getAccessRights();
      let currentRole = osparc.data.Roles.WALLET[1];
      if (accessRights.getWrite()) {
        currentRole = osparc.data.Roles.WALLET[2];
      }

      // promote/demote actions
      switch (currentRole.id) {
        case "read": {
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.WALLET[2].label);
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToAccountant", {
              gid: this.getGid(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          break;
        }
        case "write": {
          const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.WALLET[1].label);
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToMember", {
              gid: this.getGid(),
              name: this.getTitle()
            });
          });
          menu.add(demoteButton);
          break;
        }
      }

      if (menu.getChildren().length) {
        menu.addSeparator();
      }

      const removeButton = new qx.ui.menu.Button(this.tr("Remove ") + currentRole.label).set({
        textColor: "danger-red"
      });
      removeButton.addListener("execute", () => {
        this.fireDataEvent("removeMember", {
          gid: this.getGid(),
          name: this.getTitle()
        });
      });
      menu.add(removeButton);

      return menu;
    }
  }
});

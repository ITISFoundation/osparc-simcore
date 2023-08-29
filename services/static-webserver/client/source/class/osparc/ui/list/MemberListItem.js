/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2020 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (odeimaiz)

************************************************************************ */

qx.Class.define("osparc.ui.list.MemberListItem", {
  extend: osparc.ui.list.ListItemWithMenu,

  events: {
    "promoteToMember": "qx.event.type.Data",
    "promoteToManager": "qx.event.type.Data",
    "promoteToAdministrator": "qx.event.type.Data",
    "demoteToUser": "qx.event.type.Data",
    "demoteToMember": "qx.event.type.Data",
    "demoteToManager": "qx.event.type.Data",
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
    _getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const options = this.getOptions();
      if (options === null) {
        return menu;
      }

      if (options.includes("promoteToMember")) {
        const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.ORG[1].label);
        promoteButton.addListener("execute", () => {
          this.fireDataEvent("promoteToMember", {
            id: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(promoteButton);
      }
      if (options.includes("promoteToManager")) {
        const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.ORG[2].label);
        promoteButton.addListener("execute", () => {
          this.fireDataEvent("promoteToManager", {
            id: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(promoteButton);
      }
      if (options.includes("promoteToAdministrator")) {
        const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.ORG[3].label);
        promoteButton.addListener("execute", () => {
          this.fireDataEvent("promoteToAdministrator", {
            id: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(promoteButton);
      }
      if (options.includes("demoteToUser")) {
        const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.ORG[0].label);
        demoteButton.addListener("execute", () => {
          this.fireDataEvent("demoteToUser", {
            id: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(demoteButton);
      }
      if (options.includes("demoteToMember")) {
        const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.ORG[1].label);
        demoteButton.addListener("execute", () => {
          this.fireDataEvent("demoteToMember", {
            id: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(demoteButton);
      }
      if (options.includes("demoteToManager")) {
        const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.ORG[2].label);
        demoteButton.addListener("execute", () => {
          this.fireDataEvent("demoteToManager", {
            id: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(demoteButton);
      }

      if (menu.getChildren().length) {
        menu.addSeparator();
      }

      if (options.includes("removeMember")) {
        const accessRights = this.getAccessRights();
        let currentRole = "";
        if (accessRights) {
          currentRole = osparc.data.Roles.ORG[0];
          if (accessRights.getDelete()) {
            currentRole = osparc.data.Roles.ORG[3];
          } else if (accessRights.getWrite()) {
            currentRole = osparc.data.Roles.ORG[2];
          } else if (accessRights.getRead()) {
            currentRole = osparc.data.Roles.ORG[1];
          }
        }
        const removeButton = new qx.ui.menu.Button(this.tr("Remove ") + currentRole.label).set({
          textColor: "danger-red"
        });
        removeButton.addListener("execute", () => {
          this.fireDataEvent("removeMember", {
            id: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(removeButton);
      }

      return menu;
    }
  }
});

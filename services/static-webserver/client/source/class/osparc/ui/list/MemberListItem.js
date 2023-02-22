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
  extend: osparc.ui.list.ListItem,

  properties: {
    accessRights: {
      check: "Object",
      apply: "__applyAccessRights",
      event: "changeAccessRights",
      nullable: true
    },

    showOptions: {
      check: "Boolean",
      apply: "__applyShowOptions",
      event: "changeShowOptions",
      nullable: true
    }
  },

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

    __applyAccessRights: function(value) {
      if (value === null) {
        return;
      }

      this.__setSubtitle();

      const menu = this.__getOptionsMenu();
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setMenu(menu);
    },

    __setSubtitle: function() {
      const accessRights = this.getAccessRights();
      const subtitle = this.getChildControl("contact");
      if (accessRights.getDelete()) {
        subtitle.setValue(osparc.data.Roles.ORG[3].longLabel);
      } else if (accessRights.getWrite()) {
        subtitle.setValue(osparc.data.Roles.ORG[2].longLabel);
      } else if (accessRights.getRead()) {
        subtitle.setValue(osparc.data.Roles.ORG[1].longLabel);
      } else {
        subtitle.setValue(osparc.data.Roles.ORG[0].longLabel);
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const accessRights = this.getAccessRights();
      let currentRole = osparc.data.Roles.ORG[0];
      if (accessRights.getDelete()) {
        currentRole = osparc.data.Roles.ORG[3];
      } else if (accessRights.getWrite()) {
        currentRole = osparc.data.Roles.ORG[2];
      } else if (accessRights.getRead()) {
        currentRole = osparc.data.Roles.ORG[1];
      }

      // promote/demote actions
      switch (currentRole.id) {
        case "noRead": {
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.ORG[1].label);
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToMember", {
              id: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          break;
        }
        case "read": {
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.ORG[2].label);
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToManager", {
              id: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.ORG[0].label);
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToUser", {
              id: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(demoteButton);
          break;
        }
        case "write": {
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to ") + osparc.data.Roles.ORG[3].label);
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToAdministrator", {
              id: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.ORG[1].label);
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToMember", {
              id: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(demoteButton);
          break;
        }
        case "delete": {
          const demoteButton = new qx.ui.menu.Button(this.tr("Demote to ") + osparc.data.Roles.ORG[2].label);
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToManager", {
              id: this.getKey(),
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
          id: this.getKey(),
          name: this.getTitle()
        });
      });
      menu.add(removeButton);

      return menu;
    },

    __applyShowOptions: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setVisibility(value ? "visible" : "excluded");
    },

    _filter: function() {
      this.exclude();
    },

    _unfilter: function() {
      this.show();
    },

    _shouldApplyFilter: function(data) {
      if (data.name) {
        const checks = [
          this.getTitle(),
          this.getSubtitleMD()
        ];
        // data.name comes lowercased
        if (checks.filter(check => check.toLowerCase().includes(data.name)).length == 0) {
          return true;
        }
      }
      return false;
    },

    _shouldReactToFilter: function(data) {
      if (data.name && data.name.length > 1) {
        return true;
      }
      return false;
    }
  }
});

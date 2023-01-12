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

  construct: function() {
    this.base(arguments);
  },

  properties: {
    accessRights: {
      check: "Object",
      apply: "_applyAccessRights",
      event: "changeAccessRights",
      nullable: true
    },

    showOptions: {
      check: "Boolean",
      apply: "_applyShowOptions",
      event: "changeShowOptions",
      nullable: true
    }
  },

  events: {
    "promoteToMember": "qx.event.type.Data",
    "demoteToReader": "qx.event.type.Data",
    "promoteToManager": "qx.event.type.Data",
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

    _applyAccessRights: function(value) {
      if (value === null) {
        return;
      }
      const subtitle = this.getChildControl("contact");
      if (value.getDelete()) {
        subtitle.setValue(this.tr("Administrator"));
      } else if (value.getWrite()) {
        subtitle.setValue(this.tr("Manager"));
      } else if (value.getRead()) {
        subtitle.setValue(this.tr("Member"));
      } else {
        subtitle.setValue(this.tr("No Read access"));
      }
    },

    _applyShowOptions: function(value) {
      const optionsMenu = this.getChildControl("options");
      optionsMenu.setVisibility(value ? "visible" : "excluded");
      if (value) {
        const menu = this.__getOptionsMenu();
        optionsMenu.setMenu(menu);
      }
    },

    __getOptionsMenu: function() {
      const menu = new qx.ui.menu.Menu().set({
        position: "bottom-right"
      });

      const accessRights = this.getAccessRights();
      if (accessRights) {
        if (
          !accessRights.getRead() &&
          !accessRights.getDelete() &&
          !accessRights.getWrite()
        ) {
          // no read access
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to Member"));
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToMember", {
              key: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
        } else if (
          accessRights.getRead() &&
          !accessRights.getDelete() &&
          !accessRights.getWrite()
        ) {
          // member
          const promoteButton = new qx.ui.menu.Button(this.tr("Promote to Manager"));
          promoteButton.addListener("execute", () => {
            this.fireDataEvent("promoteToManager", {
              key: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(promoteButton);
          const demoteButton = new qx.ui.menu.Button(this.tr("Demote to Reader"));
          demoteButton.addListener("execute", () => {
            this.fireDataEvent("demoteToReader", {
              key: this.getKey(),
              name: this.getTitle()
            });
          });
          menu.add(demoteButton);
        }
      }

      const removeButton = new qx.ui.menu.Button(this.tr("Remove Member"));
      removeButton.addListener("execute", () => {
        this.fireDataEvent("removeMember", {
          key: this.getKey(),
          name: this.getTitle()
        });
      });
      menu.add(removeButton);

      return menu;
    }
  }
});

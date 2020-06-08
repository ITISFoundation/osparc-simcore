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

qx.Class.define("osparc.dashboard.OrgMemberListItem", {
  extend: osparc.dashboard.ServiceBrowserListItem,

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
    "promoteOrgMember": "qx.event.type.Data",
    "removeOrgMember": "qx.event.type.Data"
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
          osparc.utils.Utils.setIdToWidget(control, "studyItemMenuButton");
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
      } else {
        subtitle.setValue(this.tr("Member"));
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
      if (accessRights && !accessRights.getDelete() && !accessRights.getWrite()) {
        const promoteButton = new qx.ui.menu.Button(this.tr("Promote to Manager"));
        promoteButton.addListener("execute", () => {
          this.fireDataEvent("promoteOrgMember", {
            key: this.getKey(),
            name: this.getTitle()
          });
        });
        menu.add(promoteButton);
      }

      const removeButton = new qx.ui.menu.Button(this.tr("Remove Member"));
      removeButton.addListener("execute", () => {
        this.fireDataEvent("removeOrgMember", {
          key: this.getKey(),
          name: this.getTitle()
        });
      });
      menu.add(removeButton);

      return menu;
    }
  }
});

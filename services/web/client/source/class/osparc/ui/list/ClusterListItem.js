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

qx.Class.define("osparc.ui.list.ClusterListItem", {
  extend: osparc.ui.list.ListItem,

  construct: function() {
    this.base(arguments);
  },

  properties: {
    members: {
      check: "Object",
      nullable: false,
      apply: "__applyMembers",
      event: "changeMembers"
    },

    accessRights: {
      check: "Object",
      nullable: false,
      apply: "__applyAccessRights",
      event: "changeAcessRights"
    },

    endpoint: {
      check: "String",
      nullable: false,
      event: "changeEndpoint"
    },

    simpleAuthenticationUsername: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeSimpleAuthenticationUsername"
    },

    simpleAuthenticationPassword: {
      check: "String",
      init: "",
      nullable: false,
      event: "changeSimpleAuthenticationPassword"
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

    __applyMembers: function(members) {
      if (members === null) {
        return;
      }

      const nMembers = this.getMembersList().length + this.tr(" members");
      this.setContact(nMembers);

      const myGid = osparc.auth.Data.getInstance().getGroupId();
      if ("get"+myGid in members) {
        this.setAccessRights(members.get(myGid));
      }
    },

    getMembersList: function() {
      const membersList = [];
      const members = this.getMembers();
      const memberGids = members.basename.split("|");
      memberGids.forEach(memberGid => {
        const member = members.get(memberGid);
        member.gid = memberGid;
        membersList.push(member);
      });
      return membersList;
    },

    __applyAccessRights: function(accessRights) {
      if (accessRights === null) {
        return;
      }

      if (accessRights.getDelete()) {
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

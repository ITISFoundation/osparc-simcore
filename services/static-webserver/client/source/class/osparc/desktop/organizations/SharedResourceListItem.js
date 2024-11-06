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

qx.Class.define("osparc.desktop.organizations.SharedResourceListItem", {
  extend: osparc.ui.list.ListItemWithMenu,

  construct: function(resourceType) {
    this.__resourceType = resourceType;

    this.base(arguments);
  },

  properties: {
    orgId: {
      check: "Integer",
      init: true,
      nullable: false,
      event: "changeOrgId"
    },

    version: {
      check: "String",
      init: true,
      nullable: true,
      event: "changeVersion"
    }
  },

  events: {
    "openMoreInfo": "qx.event.type.Data"
  },

  statics: {
    canDelete: function(accessRights) {
      const canDelete = accessRights.getDelete ? accessRights.getDelete() : false;
      return canDelete;
    },

    canWrite: function(accessRights) {
      let canWrite = accessRights.getWrite ? accessRights.getWrite() : false;
      canWrite = canWrite || (accessRights.getWriteAccess ? accessRights.getWriteAccess() : false);
      return canWrite;
    },

    canRead: function(accessRights) {
      let canRead = accessRights.getRead ? accessRights.getRead() : false;
      canRead = canRead || (accessRights.getExecuteAccess ? accessRights.getExecuteAccess() : false);
      return canRead;
    }
  },

  members: {
    __resourceType: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "info-button": {
          control = new qx.ui.form.Button().set({
            maxWidth: 28,
            maxHeight: 28,
            alignX: "center",
            alignY: "middle",
            icon: "@MaterialIcons/info_outline/14",
            focusable: false
          });
          this._add(control, {
            row: 0,
            column: 4,
            rowSpan: 2
          });
          break;
        }
      }

      return control || this.base(arguments, id);
    },

    __getRoleInfo: function(i) {
      if (this.__resourceType === "service") {
        return osparc.data.Roles.SERVICES[i];
      }
      return osparc.data.Roles.STUDY[i];
    },

    // overridden
    _setRole: function() {
      const accessRights = this.getAccessRights();
      const role = this.getChildControl("role");
      if (this.self().canDelete(accessRights)) {
        role.setValue(this.__getRoleInfo(3).label);
      } else if (this.self().canWrite(accessRights)) {
        role.setValue(this.__getRoleInfo(2).label);
      } else {
        role.setValue(this.__getRoleInfo(1).label);
      }
    },

    // overridden
    _getInfoButton: function() {
      const accessRights = this.getAccessRights();
      if (
        ("getRead" in accessRights && accessRights.getRead()) ||
        ("getExecute" in accessRights && accessRights.getExecute())
      ) {
        const button = this.getChildControl("info-button");
        button.addListener("execute", () => this.fireDataEvent("openMoreInfo", {
          key: this.getKey(),
          version: this.getVersion()
        }));
        return button;
      }
      return null;
    }
  }
});

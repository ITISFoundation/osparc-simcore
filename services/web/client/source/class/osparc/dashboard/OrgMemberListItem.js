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

    showRemove: {
      check: "Boolean",
      apply: "_applyShowRemove",
      event: "changeShowRemove",
      nullable: true
    }
  },

  events: {
    "removeOrgMember": "qx.event.type.Data"
  },

  members: {
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "remove": {
          const iconSize = 28;
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/trash/"+(iconSize-14)).set({
            alignX: "center",
            alignY: "middle",
            maxWidth: iconSize,
            maxHeight: iconSize
          });
          control.addListener("execute", () => {
            this.fireDataEvent("removeOrgMember", {
              key: this.getKey(),
              name: this.getTitle()
            });
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
      const subtitle = this.getChildControl("subtitle");
      if (value.getDelete()) {
        subtitle.setValue("SuperManager");
      } else if (value.getWrite()) {
        subtitle.setValue("Manager");
      } else {
        subtitle.setValue("Member");
      }
    },

    _applyShowRemove: function(value) {
      const removeBtn = this.getChildControl("remove");
      removeBtn.setVisibility(value ? "visible" : "excluded");
    }
  }
});

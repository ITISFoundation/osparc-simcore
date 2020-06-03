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
            this.fireDataEvent("removeOrgMember", this.getKey());
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

    _applyShowRemove: function(value) {
      const label = this.getChildControl("remove");
      label.setVisibility(value ? "visible" : "excluded");
    }
  }
});

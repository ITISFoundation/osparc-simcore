/* ************************************************************************

   qxapp - the simcore frontend

   https://simcore.io

   Copyright:
     2018 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Odei Maiz (maiz)

************************************************************************ */

qx.Class.define("qxapp.component.EntityListItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  properties: {
    entityId: {
      check: "String",
      nullable: true
    },

    pathId: {
      check: "String",
      nullable: true
    },

    pathLabel: {
      check: "String",
      nullable: true
    },

    checked: {
      check: "Boolean",
      event: "changeChecked",
      nullable: true
    }
  },

  events: {
    "visibilityChanged": "qx.event.type.Data"
  },

  members : {
    __checkbox : null,

    _addWidgets : function() {
      // Here's our indentation and tree-lines
      this.addSpacer();
      this.addOpenButton();

      // The standard tree icon follows
      this.addIcon();

      // A checkbox comes right after the tree icon
      var checkbox = this.__checkbox = new qx.ui.form.CheckBox();
      this.bind("checked", checkbox, "value");
      checkbox.bind("value", this, "checked");
      checkbox.setFocusable(false);
      checkbox.setTriState(true);
      checkbox.setMarginRight(4);
      checkbox.addListener("changeValue", e => {
        const data = {
          entityId: this.getEntityId(),
          show: e.getData()
        };
        this.fireDataEvent("visibilityChanged", data);
      }, this);
      this.addWidget(checkbox);

      // The label
      this.addLabel();
    }
  }
});

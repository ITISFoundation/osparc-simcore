/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 */

qx.Class.define("osparc.component.filter.TreeFilterItem", {
  extend: qx.ui.tree.VirtualTreeItem,
  properties: {
    checked: {
      check: "Boolean",
      init: false,
      event: "changeChecked",
      nullable: true
    }
  },
  members: {
    _addWidgets: function() {
      this.addSpacer();
      this.addOpenButton();
      this._add(this.getChildControl("checkbox"));
      this.addLabel();
    },
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "checkbox":
          control = new qx.ui.form.CheckBox();
          control.setTriState(true);
          this.bind("checked", control, "value");
          control.bind("value", this, "checked");
      }
      return control || this.base(arguments, id);
    }
  }
});

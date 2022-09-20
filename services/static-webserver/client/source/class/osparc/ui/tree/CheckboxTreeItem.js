/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.ui.tree.CheckboxTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,
  include: osparc.ui.tree.MHintInTree,

  properties: {
    checked: {
      check: "Boolean",
      init: false,
      event: "changeChecked",
      nullable: true
    }
  },

  events: {
    checkboxClicked: "qx.event.type.Event"
  },

  members: {
    _addWidgets: function() {
      this.addSpacer();
      this.addOpenButton();
      this._add(this.getChildControl("checkbox"));
      const label = this.getChildControl("label");
      this._add(label, {
        flex: 1
      });
      this._add(new qx.ui.core.Spacer(), {
        flex: 1
      });
      this.addHint();

      this.setMaxWidth(240);
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "checkbox":
          control = new qx.ui.form.CheckBox();
          control.setTriState(true);
          control.bind("value", this, "checked");
          this.bind("checked", control, "value");
          control.addListener("tap", () => this.fireEvent("checkboxClicked"));
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});

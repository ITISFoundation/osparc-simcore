/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2020 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.ui.tree.CheckboxTreeItem", {
  extend: qx.ui.tree.VirtualTreeItem,

  properties: {
    checked: {
      check: "Boolean",
      init: false,
      event: "changeChecked",
      nullable: true
    },

    nItems: {
      check: "Number",
      init: 0,
      event: "changeNItems",
      nullable: false
    },

    showNItems: {
      check: "Boolean",
      init: true,
      event: "changeShowNItems",
      nullable: false
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
      this.addLabel();

      // All else should be right justified
      this.addWidget(new qx.ui.core.Spacer(), {
        flex: 1
      });

      this._add(this.getChildControl("number-items"));
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
        case "number-items":
          control = new qx.ui.basic.Label().set({
            visibility: "excluded"
          });
          this.bind("showNItems", control, "visibility", {
            converter: value => value ? "visible" : "excluded"
          });
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});

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

    description: {
      check: "String",
      init: null,
      event: "changeDescription",
      apply: "__recreateInfoButton",
      nullable: true
    },

    url: {
      check: "String",
      init: null,
      event: "changeUrl",
      apply: "__recreateInfoButton",
      nullable: true
    }
  },

  events: {
    checkboxClicked: "qx.event.type.Event"
  },

  members: {
    __infoButton: null,

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
          control.bind("value", this, "checked");
          this.bind("checked", control, "value");
          control.addListener("tap", () => this.fireEvent("checkboxClicked"));
          break;
      }
      return control || this.base(arguments, id);
    },

    __recreateInfoButton: function() {
      if (this.__infoButton) {
        this._remove(this.__infoButton);
      }
      const desc = this.getDescription();
      const url = this.getUrl();
      const hints = [];
      if (desc !== "" && desc !== null) {
        hints.push(desc);
      }
      if (url !== "" && url !== null) {
        const link = "<a href=" + url + " target='_blank'>More...</a>";
        hints.push(link);
      }
      if (hints.length) {
        const hint = hints.join("<br>");
        this.__infoButton = new osparc.component.form.FieldWHint("", hint, new qx.ui.basic.Label("")).set({
          maxWidth: 150
        });
        this._add(this.__infoButton);
      }
    }
  }
});

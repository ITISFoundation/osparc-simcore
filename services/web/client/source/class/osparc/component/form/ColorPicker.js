/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2022 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

/**
 * Represents one tag in the preferences page.
 */
qx.Class.define("osparc.component.form.ColorPicker", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this.__validationManager = new qx.ui.form.validation.Manager();
    this._add(this.getChildControl("color-button"));
    this._add(this.getChildControl("color-input"));
  },

  properties: {
    color: {
      check: "Color",
      event: "changeColor",
      init: "#303030"
    }
  },

  members: {
    __validationManager: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "color-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/sync-alt/12");
          control.addListener("execute", () => {
            this.getChildControl("color-input").setValue(osparc.utils.Utils.getRandomColor());
          }, this);
          break;
        case "color-input":
          control = new qx.ui.form.TextField().set({
            width: 60,
            required: true
          });
          this.bind("color", control, "value");
          control.bind("value", this.getChildControl("color-button"), "backgroundColor");
          control.bind("value", this.getChildControl("color-button"), "textColor", {
            converter: value => osparc.utils.Utils.getContrastedTextColor(qx.theme.manager.Color.getInstance().resolve(value))
          });
          this.__validationManager.add(control, osparc.utils.Validators.hexColor);
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});

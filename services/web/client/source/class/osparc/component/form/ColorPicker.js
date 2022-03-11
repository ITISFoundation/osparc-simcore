/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2022 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.component.form.ColorPicker", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

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
          control.addListener("execute", () => this.setColor(osparc.utils.Utils.getRandomColor()), this);
          this.bind("color", control, "backgroundColor");
          this.bind("color", control, "textColor", {
            converter: value => osparc.utils.Utils.getContrastedTextColor(qx.theme.manager.Color.getInstance().resolve(value))
          });
          break;
        case "color-input":
          control = new qx.ui.form.TextField().set({
            width: 60,
            required: true
          });
          this.bind("color", control, "value");
          control.addListener("changeValue", e => {
            const newColor = e.getData();
            if (osparc.utils.Validators.hexColor(newColor, control)) {
              this.setColor(newColor);
            }
          });
          break;
      }
      return control || this.base(arguments, id);
    }
  }
});

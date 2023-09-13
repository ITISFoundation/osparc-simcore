/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2022 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.form.ColorPicker", {
  extend: qx.ui.core.Widget,

  construct: function() {
    this.base(arguments);

    this._setLayout(new qx.ui.layout.HBox());

    this._add(this.getChildControl("random-button"));
    this._add(this.getChildControl("selector-button"));
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
    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "random-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/sync-alt/12");
          control.addListener("execute", () => this.setColor(osparc.utils.Utils.getRandomColor()), this);
          this.bind("color", control, "backgroundColor");
          this.bind("color", control, "textColor", {
            converter: value => qx.theme.manager.Color.getInstance().resolve(osparc.utils.Utils.getContrastedTextColor(value))
          });
          break;
        case "selector-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye-dropper/12");
          control.addListener("execute", () => this.__openColorSelector(), this);
          this.bind("color", control, "backgroundColor");
          this.bind("color", control, "textColor", {
            converter: value => qx.theme.manager.Color.getInstance().resolve(osparc.utils.Utils.getContrastedTextColor(value))
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
    },

    __openColorSelector: function() {
      const colorSelector = new qx.ui.control.ColorSelector();
      const rgb = qx.util.ColorUtil.hexStringToRgb(this.getColor());
      colorSelector.setRed(rgb[0]);
      colorSelector.setGreen(rgb[1]);
      colorSelector.setBlue(rgb[2]);
      osparc.ui.window.Window.popUpInWindow(colorSelector, this.tr("Pick a color"), 590, 380);
      colorSelector.addListener("changeValue", e => this.setColor(e.getData()));
    }
  }
});

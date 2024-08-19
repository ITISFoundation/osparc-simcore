/*
 * oSPARC - The SIMCORE frontend - https://osparc.io
 * Copyright: 2022 IT'IS Foundation - https://itis.swiss
 * License: MIT - https://opensource.org/licenses/MIT
 * Authors: Ignacio Pascual (ignapas)
 *          Odei Maiz (odeimaiz)
 */

qx.Class.define("osparc.form.ColorPicker", {
  extend: qx.ui.core.Widget,
  include : [
    qx.ui.form.MForm
  ],
  implement : [
    qx.ui.form.IStringForm,
    qx.ui.form.IForm
  ],

  construct: function() {
    this.base(arguments);

    const layout = new qx.ui.layout.HBox();
    this._setLayout(layout);

    this.getChildControl("random-button");
    this.getChildControl("selector-button");
    this.getChildControl("color-input");
  },

  properties: {
    value: {
      check: "Color",
      event: "changeValue",
      init: "#303030"
    }
  },

  // eslint-disable-next-line qx-rules/no-refs-in-members
  members: {
    _forwardStates: {
      focused : true,
      invalid : true
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "random-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/sync-alt/12");
          control.addListener("execute", () => this.setValue(osparc.utils.Utils.getRandomColor()), this);
          this.bind("value", control, "backgroundColor");
          this.bind("value", control, "textColor", {
            converter: value => qx.theme.manager.Color.getInstance().resolve(osparc.utils.Utils.getContrastedTextColor(value))
          });
          this._add(control);
          break;
        case "selector-button":
          control = new qx.ui.form.Button(null, "@FontAwesome5Solid/eye-dropper/12");
          control.addListener("execute", () => this.__openColorSelector(), this);
          this.bind("value", control, "backgroundColor");
          this.bind("value", control, "textColor", {
            converter: value => qx.theme.manager.Color.getInstance().resolve(osparc.utils.Utils.getContrastedTextColor(value))
          });
          this._add(control);
          break;
        case "color-input":
          control = new qx.ui.form.TextField().set({
            width: 80,
            required: true
          });
          this._add(control, {
            flex: 1
          });
          this.bind("value", control, "value");
          control.addListener("changeValue", e => {
            const newColor = e.getData();
            if (osparc.utils.Validators.hexColor(newColor, control)) {
              this.setValue(newColor);
            }
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __openColorSelector: function() {
      const colorSelector = new qx.ui.control.ColorSelector();
      const rgb = qx.util.ColorUtil.hexStringToRgb(this.getValue());
      colorSelector.setRed(rgb[0]);
      colorSelector.setGreen(rgb[1]);
      colorSelector.setBlue(rgb[2]);
      osparc.ui.window.Window.popUpInWindow(colorSelector, this.tr("Pick a color"), 590, 380);
      colorSelector.addListener("changeValue", e => this.setValue(e.getData()));
    },

    // overridden
    resetValue: function() {
      this.getChildControl("color-input").resetValue();
    },

    // overridden
    focus: function() {
      this.base(arguments);
      this.getChildControl("color-input").getFocusElement().focus();
    },

    // overridden
    tabFocus: function() {
      const field = this.getChildControl("color-input");
      field.getFocusElement().focus();
      field.selectAllText();
    },
  }
});

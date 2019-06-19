/* ************************************************************************

   qxapp - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

qx.Class.define("qxapp.component.form.TextFieldWHint", {
  extend: qx.ui.core.Widget,

  /**
   * Text field with a hint tooltip
   *
   * @extends qx.ui.core.Widget
   */
  construct: function(value, textfield, hint) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Canvas());

    this.__textField = textfield || new qx.ui.form.TextField();
    if (value) {
      this.__textField.setValue(value);
    }
    this.getChildControl("textfield");
    this.__infoButton = this.getChildControl("infobutton");

    this.__attachEventHandlers();
  },

  members: {
    __textField: null,
    __hint: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "textfield":
          control = this.__textField;
          this._add(control, {
            top: 0,
            right: 0,
            bottom: 0,
            left: 0
          });
          break;
        case "infobutton":
          control = new qxapp.component.form.IconButton("@FontAwesome5Solid/info-circle/14").set({
            visibility: "excluded"
          });
          this._add(control, {
            right: 0,
            bottom: 5
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __attachEventHandlers: function() {
      this.__textField.addListener("focus", () => this.__infoButton.show(), this);
      this.__textField.addListener("focusout", () => this.__infoButton.exclude(), this);
      this.__infoButton.addListener("mouseover", () => {
        this.__hint = qxapp.component.hint.HintManager.getHint(this.__infoButton, "Lorem ipsum sit amet");
      }, this);
      this.__infoButton.addListener("mouseout", () => this.__hint.destroy(), this);
    }
  }
});
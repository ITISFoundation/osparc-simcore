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

qx.Class.define("qxapp.component.form.FieldWHint", {
  extend: qx.ui.core.Widget,

  /**
   * Text field with a hint tooltip
   *
   * @extends qx.ui.core.Widget
   */
  construct: function(value, hint, field) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.HBox(5).set({
      alignY: "middle"
    }));

    this.__field = field || new qx.ui.form.TextField();
    if (value) {
      this.__field.setValue(value);
    }
    this._add(this.__field, {
      flex: 1
    });

    if (hint) {
      this.__hintText = hint;
    }
    this.__infoButton = this.getChildControl("infobutton");

    this.__attachEventHandlers();
  },

  members: {
    __field: null,
    __hint: null,
    __hintText: null,
    __infoButton: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "infobutton":
          control = new qxapp.component.form.IconButton("@FontAwesome5Solid/info-circle/14").set({
            visibility: "hidden"
          });
          this._add(control);
          break;
      }
      return control || this.base(arguments, id);
    },

    __attachEventHandlers: function() {
      if (this.__hintText) {
        this.__field.addListener("focus", () => this.__infoButton.show(), this);
        this.__field.addListener("focusout", () => this.__infoButton.hide(), this);
        this.__infoButton.addListener("mouseover", () => {
          this.__hint = qxapp.component.hint.HintManager.getHint(this.__infoButton, this.__hintText);
        }, this);
        this.__infoButton.addListener("mouseout", () => this.__hint.destroy(), this);
      }
    },

    getField: function() {
      return this.__field;
    }
  }
});
/* ************************************************************************

   osparc - the simcore frontend

   https://osparc.io

   Copyright:
     2019 IT'IS Foundation, https://itis.swiss

   License:
     MIT: https://opensource.org/licenses/MIT

   Authors:
     * Ignacio Pascual (ignapas)

************************************************************************ */

/**
 * @asset(hint/hint.css)
 */

qx.Class.define("osparc.component.form.FieldWHint", {
  extend: qx.ui.core.Widget,

  /**
   * Text field with a hint tooltip
   *
   * @extends qx.ui.core.Widget
   */
  construct: function(value, hint, field) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Canvas());

    this.__field = field || new qx.ui.form.TextField();
    if (value) {
      this.__field.setValue(value);
    }
    this.__field.setPaddingRight(18);
    this.getContentElement().addClass("hint-input");
    this.__field.getContentElement().addClass("hint-field");
    this._add(this.__field, {
      top: 0,
      right: 0,
      bottom: 0,
      left: 0
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
          control = new osparc.component.form.IconButton("@FontAwesome5Solid/info-circle/14");
          control.getContentElement().addClass("hint-button");
          this._add(control, {
            right: 0,
            bottom: 5
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __attachEventHandlers: function() {
      if (this.__hintText) {
        this.__hint = new osparc.ui.hint.Hint(this.__infoButton, this.__hintText).set({
          active: false
        });
        this.__infoButton.addListener("mouseover", () => this.__hint.show(), this);
        this.__infoButton.addListener("mouseout", () => this.__hint.exclude(), this);

        this.__field.bind("visibility", this, "visibility");
      }
    },

    getField: function() {
      return this.__field;
    }
  }
});

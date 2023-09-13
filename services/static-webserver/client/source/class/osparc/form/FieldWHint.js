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

qx.Class.define("osparc.form.FieldWHint", {
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

    this.__infoButton = this.getChildControl("infobutton");
    if (hint) {
      this.__infoButton.setHintText(hint);
    }

    this.__field.bind("visibility", this, "visibility");
  },

  properties: {
    hintPosition: {
      check: ["left", "right"],
      init: "right",
      apply: "__applyHintPosition"
    }
  },

  statics: {
    TOP_MARGIN: 3
  },

  members: {
    __field: null,
    __infoButton: null,

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "infobutton":
          control = new osparc.ui.hint.InfoHint();
          this._add(control, {
            right: 0,
            top: this.self().TOP_MARGIN
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __applyHintPosition: function(value) {
      this._removeAll();
      this._add(this.__field, {
        top: 0,
        right: 0,
        bottom: 0,
        left: value === "left" ? 18 : 0
      });
      if (value === "left") {
        this._add(this.__infoButton, {
          left: 0,
          top: this.self().TOP_MARGIN
        });
      } else {
        this._add(this.__infoButton, {
          right: 0,
          top: this.self().TOP_MARGIN
        });
      }
    }
  }
});

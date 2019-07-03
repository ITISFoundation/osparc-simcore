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

/**
 * @asset(hint/hint.css)
 */

qx.Class.define("qxapp.component.form.FieldWHint", {
  extend: qx.ui.core.Widget,

  /**
   * Text field with a hint tooltip
   *
   * @extends qx.ui.core.Widget
   */
  construct: function(value, hint, field) {
    this.base(arguments);
    this._setLayout(new qx.ui.layout.Canvas());

    const hintCssUri = qx.util.ResourceManager.getInstance().toUri("hint/hint.css");
    qx.module.Css.includeStylesheet(hintCssUri);

    this.__field = field || new qx.ui.form.TextField();
    if (value) {
      this.__field.setValue(value);
    }
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
          control = new qxapp.component.form.IconButton("@FontAwesome5Solid/info-circle/14");
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
        this.addListener("mouseover", () => this.__field.setPaddingRight(18), this);
        this.addListener("mouseout", () => this.__field.resetPaddingRight(), this);
        this.__infoButton.addListener("mouseover", () => this.__hint = new qxapp.ui.hint.Hint(this.__infoButton, this.__hintText), this);
        this.__infoButton.addListener("mouseout", () => this.__hint.destroy(), this);

        this.__field.bind("visibility", this, "visibility");
      }
    },

    getField: function() {
      return this.__field;
    }
  }
});

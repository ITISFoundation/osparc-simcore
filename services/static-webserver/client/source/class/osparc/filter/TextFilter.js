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
 * TextField to make a simple text filter.
 */
qx.Class.define("osparc.filter.TextFilter", {
  extend: osparc.filter.UIFilter,

  /**
   * Constructor for the TextFilter takes UIFilters mandatory params plus an optional translation id for its label.
   *
   * @extends osparc.filter.UIFilter
   */
  construct: function(filterId, filterGroupId) {
    this.base(arguments, filterId, filterGroupId);
    this._setLayout(new qx.ui.layout.Canvas());

    this.set({
      allowStretchX: false,
      allowStretchY: false
    });

    this.__textField = this.getChildControl("textfield");

    this.getChildControl("clearbutton");

    this.__attachEventHandlers();
  },

  properties: {
    appearance: {
      refine: true,
      init: "textfilter"
    }
  },

  members: {
    __textField: null,

    /**
     * Function that resets the field and dispatches the update.
     */
    reset: function() {
      this.__textField.resetValue();
      this.__textField.fireDataEvent("input", "");
    },

    _createChildControlImpl: function(id) {
      let control;
      switch (id) {
        case "textfield":
          control = new qx.ui.form.TextField().set({
            paddingRight: 15,
            placeholder: this.tr("Filter")
          });
          control.getContentElement().setAttribute("autocomplete", "off");
          // FIXME: autocomplete "off" doesn't work on Chrome
          // https://www.codementor.io/leonardofaria/disabling-autofill-in-chrome-zec47xcui
          this._add(control, {
            width: "100%"
          });
          break;
        case "clearbutton":
          control = new osparc.ui.basic.IconButton("@MaterialIcons/close/12", () => {
            this.reset();
            this.__textField.focus();
          });
          this._add(control, {
            right: 0,
            bottom: 6
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __attachEventHandlers: function() {
      this.__textField.addListener("input", evt => {
        this._filterChange(evt.getData().trim().toLowerCase());
      });
    }
  }
});

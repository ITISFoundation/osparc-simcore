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
 * TextField to make a simple text filter.
 */
qx.Class.define("qxapp.component.filter.TextFilter", {
  extend: qxapp.component.filter.UIFilter,

  /**
   * Constructor for the TextFilter takes UIFilters mandatory params plus an optional translation id for its label.
   *
   * @extends qxapp.component.filter.UIFilter
   */
  construct: function(filterId, groupId) {
    this.base(arguments, filterId, groupId);
    this._setLayout(new qx.ui.layout.Canvas());

    this.__textField = this.getChildControl("textfield").set({
      placeholder: this.tr("Filter")
    });

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
            paddingRight: 15
          });
          this._add(control);
          break;
        case "clearbutton":
          control = new qxapp.component.form.IconButton("@MaterialIcons/close/12", () => this.reset());
          this._add(control, {
            right: 0,
            bottom: 12
          });
          break;
      }
      return control || this.base(arguments, id);
    },

    __attachEventHandlers: function() {
      this.__textField.addListener("input", evt => {
        this._filterChange(evt.getData().trim()
          .toLowerCase());
      });
    }
  }
});

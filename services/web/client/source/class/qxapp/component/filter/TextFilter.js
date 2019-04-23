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
   *
   * @param {string} [labelTr=Filter] Translation id used for the filter label.
   */
  construct: function(filterId, groupId, labelTr = "Filter") {
    this.base(arguments, filterId, groupId);
    this._setLayout(new qx.ui.layout.Canvas());

    this.__textField = this.getChildControl("textfield").set({
      placeholder: this.tr(labelTr)
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
